#!/usr/bin/env python3
"""
OfflineU - Self-hosted Course Viewer & Tracker
Enhanced version with dynamic subdirectory navigation
"""

import os
import json
import logging
import mimetypes
import re
import sys
import argparse
import sqlite3
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any, Tuple
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from ai_analyzer import AIAnalyzer, AI_PROVIDERS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

# Set up logging to logs/ folder with date in filename
_logs_dir = Path('logs')
_logs_dir.mkdir(exist_ok=True)
_log_date = datetime.now().strftime('%Y-%m-%d')
_log_filename = f'logs/offlineu_{_log_date}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(_log_filename, maxBytes=5_000_000, backupCount=10),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Supported file types
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.flv', '.wmv'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}
SUBTITLE_EXTENSIONS = {'.srt', '.vtt', '.ass', '.sub', '.sbv'}
TEXT_EXTENSIONS = {'.txt', '.md', '.html', '.htm', '.pdf', '.docx', '.doc', '.rtf'}
QUIZ_INDICATORS = {'quiz', 'exam', 'test', 'assessment', 'exercise', 'assignment', 'homework'}


@dataclass
class Lesson:
    title: str
    path: str
    lesson_type: str  # 'video', 'audio', 'text', 'quiz', 'mixed'
    video_file: Optional[str] = None
    audio_file: Optional[str] = None
    subtitle_file: Optional[str] = None
    text_files: List[str] = None
    completed: bool = False
    last_accessed: Optional[str] = None
    progress_seconds: int = 0
    order: int = 0

    def __post_init__(self):
        if self.text_files is None:
            self.text_files = []


@dataclass
class DirectoryNode:
    """Represents a directory in the course structure"""
    name: str
    path: str
    type: str  # 'directory' or 'lesson'
    children: Dict[str, 'DirectoryNode'] = None
    lessons: List[Lesson] = None
    completed: bool = False
    last_accessed: Optional[str] = None
    order: int = 0
    has_content: bool = False  # Whether this directory contains actual lesson content

    def __post_init__(self):
        if self.children is None:
            self.children = {}
        if self.lessons is None:
            self.lessons = []


@dataclass
class Course:
    name: str
    path: str
    root_node: DirectoryNode
    progress_file: str
    last_accessed_path: Optional[str] = None
    completion_percentage: float = 0.0

    def __post_init__(self):
        if self.root_node is None:
            self.root_node = DirectoryNode("", "", "directory")


class DynamicCourseParser:
    """Enhanced parser that builds a proper directory tree structure"""

    @staticmethod
    def scan_directory(course_path: str) -> Course:
        """Scan directory and build dynamic tree structure"""
        course_path = Path(course_path)
        if not course_path.exists() or not course_path.is_dir():
            raise ValueError(f"Invalid course path: {course_path}")

        course_name = course_path.name
        print(f"Scanning course: {course_name}")

        # Build the directory tree
        root_node = DynamicCourseParser._build_directory_tree(course_path, course_path)
        
        # Calculate completion statistics
        stats = DynamicCourseParser._calculate_completion_stats(root_node)
        
        progress_file = str(course_path / ".offlineu_progress.db")

        return Course(
            name=course_name,
            path=str(course_path),
            root_node=root_node,
            progress_file=progress_file
        )

    @staticmethod
    def _build_directory_tree(course_path: Path, current_path: Path, depth: int = 0) -> DirectoryNode:
        """Recursively build directory tree structure"""
        if depth > 10:  # Prevent infinite recursion
            return DirectoryNode(current_path.name, str(current_path), "directory")

        node_name = current_path.name if current_path != course_path else "Course Root"
        node = DirectoryNode(
            name=node_name,
            path=str(current_path),
            type="directory",
            order=depth
        )

        try:
            # Get all items in current directory
            items = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in items:
                if item.name.startswith('.'):
                    continue
                
                if item.is_dir():
                    # Recursively process subdirectory
                    child_node = DynamicCourseParser._build_directory_tree(course_path, item, depth + 1)
                    if child_node.has_content or child_node.children:
                        node.children[child_node.name] = child_node
                        node.has_content = True
                
                elif item.is_file():
                    # Process file as potential lesson content
                    lesson = DynamicCourseParser._create_lesson_from_file(item, course_path)
                    if lesson:
                        # Add lesson directly to this node's lessons list
                        node.lessons.append(lesson)
                        node.has_content = True

        except (PermissionError, OSError) as e:
            print(f"Error accessing {current_path}: {e}")

        return node

    @staticmethod
    def _create_lesson_from_file(file_path: Path, course_path: Path) -> Optional[Lesson]:
        """Create a lesson from a single file"""
        ext = file_path.suffix.lower()
        filename = file_path.name.lower()

        # Skip non-content files
        if ext in {'.log', '.tmp', '.bak', '.swp', '.DS_Store', '.Thumbs.db'}:
            return None

        # Determine lesson type and files
        video_file = None
        audio_file = None
        subtitle_file = None
        text_files = []
        lesson_type = 'text'

        # Create relative path for file serving - normalize to forward slashes
        relative_path = str(file_path.relative_to(course_path)).replace('\\', '/')

        if ext in VIDEO_EXTENSIONS:
            video_file = relative_path
            lesson_type = 'video'
            
            # Auto-detect subtitle files with matching names
            # Look for files like: video.mp4 -> video.srt, video.vtt, etc.
            file_stem = file_path.stem
            subtitle_file = DynamicCourseParser._find_matching_subtitle(file_path.parent, file_stem, course_path)
            
        elif ext in AUDIO_EXTENSIONS:
            audio_file = relative_path
            lesson_type = 'audio'
        elif ext in SUBTITLE_EXTENSIONS:
            subtitle_file = relative_path
            return None  # Don't create lessons for subtitle files alone
        elif ext in TEXT_EXTENSIONS:
            text_files.append(relative_path)
            if any(indicator in filename for indicator in QUIZ_INDICATORS):
                lesson_type = 'quiz'
        else:
            # Skip unsupported file types
            return None

        # Clean up lesson name for display
        display_name = DynamicCourseParser._clean_lesson_name(file_path.stem)

        return Lesson(
            title=display_name,
            path=str(file_path),  # Store the actual file path, not just parent
            lesson_type=lesson_type,
            video_file=video_file,
            audio_file=audio_file,
            subtitle_file=subtitle_file,
            text_files=text_files,
            order=0
        )

    @staticmethod
    def _find_matching_subtitle(directory: Path, stem: str, course_path: Path) -> Optional[str]:
        """Find a subtitle file matching the given stem in the same directory"""
        for subtitle_ext in SUBTITLE_EXTENSIONS:
            subtitle_path = directory / f"{stem}{subtitle_ext}"
            if subtitle_path.exists() and subtitle_path.is_file():
                # Return the relative path for serving
                relative_path = str(subtitle_path.relative_to(course_path)).replace('\\', '/')
                return relative_path
        return None

    @staticmethod
    def _clean_lesson_name(name: str) -> str:
        """Clean up lesson name for display"""
        # Remove common patterns
        name = re.sub(r'^\d+[\.\-_\s]*', '', name)  # Remove leading numbers
        name = re.sub(r'[-_]+', ' ', name)  # Replace dashes/underscores with spaces
        name = ' '.join(word.capitalize() for word in name.split() if word)
        return name if name.strip() else "Untitled Lesson"

    @staticmethod
    def _calculate_completion_stats(node: DirectoryNode) -> Dict[str, Any]:
        """Calculate completion statistics for a directory node"""
        total_lessons = 0
        completed_lessons = 0
        
        def count_lessons_recursive(n: DirectoryNode):
            nonlocal total_lessons, completed_lessons
            
            # Count lessons in this node
            for lesson in n.lessons:
                total_lessons += 1
                if lesson.completed:
                    completed_lessons += 1
            
            # Recursively count in children
            for child in n.children.values():
                count_lessons_recursive(child)
        
        count_lessons_recursive(node)
        
        completion_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        
        return {
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'completion_percentage': round(completion_percentage, 1)
        }


class ProgressTracker:
    """Handles progress tracking and persistence using SQLite"""

    @staticmethod
    def _get_conn(course: Course) -> sqlite3.Connection:
        conn = sqlite3.connect(course.progress_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _init_db(course: Course):
        """Create tables if they don't exist. Migrate from legacy JSON if present."""
        json_path = course.progress_file.replace('.db', '.json')
        db_exists = os.path.exists(course.progress_file)

        conn = ProgressTracker._get_conn(course)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS progress (
                    lesson_path TEXT PRIMARY KEY,
                    completed INTEGER NOT NULL DEFAULT 0,
                    progress_seconds INTEGER NOT NULL DEFAULT 0,
                    last_accessed TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.commit()

            if not db_exists and os.path.exists(json_path):
                ProgressTracker._migrate_from_json(course, conn, json_path)
        finally:
            conn.close()

    @staticmethod
    def _migrate_from_json(course: Course, conn: sqlite3.Connection, json_path: str):
        """Import progress data from legacy JSON file, then rename it to .bak."""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            for key, value in data.items():
                if key == 'last_accessed_path':
                    conn.execute(
                        'INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)',
                        ('last_accessed_path', str(value))
                    )
                elif isinstance(value, dict):
                    conn.execute(
                        'INSERT OR REPLACE INTO progress (lesson_path, completed, progress_seconds, last_accessed) VALUES (?, ?, ?, ?)',
                        (key,
                         1 if value.get('completed') else 0,
                         value.get('progress_seconds', 0),
                         value.get('last_accessed'))
                    )

            conn.commit()
            os.rename(json_path, json_path + '.bak')
            logger.info(f"Migrated progress from {json_path} to SQLite")
        except Exception as e:
            logger.error(f"Failed to migrate progress from JSON: {e}")

    @staticmethod
    def load_progress(course: Course) -> Dict[str, Any]:
        """Load progress from SQLite database. Returns same dict format as before."""
        try:
            ProgressTracker._init_db(course)
            conn = ProgressTracker._get_conn(course)
            try:
                rows = conn.execute(
                    'SELECT lesson_path, completed, progress_seconds, last_accessed FROM progress'
                ).fetchall()
                result: Dict[str, Any] = {}
                for row in rows:
                    result[row['lesson_path']] = {
                        'completed': bool(row['completed']),
                        'progress_seconds': row['progress_seconds'],
                        'last_accessed': row['last_accessed']
                    }

                meta_row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'last_accessed_path'"
                ).fetchone()
                if meta_row:
                    result['last_accessed_path'] = meta_row['value']

                return result
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error loading progress: {e}")
            return {}

    @staticmethod
    def save_progress(course: Course, progress_data: Dict[str, Any]):
        """Save full progress dict to SQLite (batch upsert)."""
        try:
            ProgressTracker._init_db(course)
            conn = ProgressTracker._get_conn(course)
            try:
                for key, value in progress_data.items():
                    if key == 'last_accessed_path':
                        conn.execute(
                            'INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)',
                            ('last_accessed_path', str(value))
                        )
                    elif isinstance(value, dict):
                        conn.execute(
                            'INSERT OR REPLACE INTO progress (lesson_path, completed, progress_seconds, last_accessed) VALUES (?, ?, ?, ?)',
                            (key,
                             1 if value.get('completed') else 0,
                             value.get('progress_seconds', 0),
                             value.get('last_accessed'))
                        )
                conn.commit()
                logger.info(f"Progress saved: {course.progress_file}")
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error saving progress to {course.progress_file}: {e}")

    @staticmethod
    def update_lesson_progress(course: Course, lesson_path: str, completed: bool = False, progress_seconds: int = 0):
        """Update progress for specific lesson by path (single upsert, no load required)."""
        logger.info(f"Updating progress: path={lesson_path!r}, completed={completed}, seconds={progress_seconds}")
        ProgressTracker._init_db(course)
        conn = ProgressTracker._get_conn(course)
        try:
            conn.execute(
                'INSERT OR REPLACE INTO progress (lesson_path, completed, progress_seconds, last_accessed) VALUES (?, ?, ?, ?)',
                (lesson_path, 1 if completed else 0, progress_seconds, datetime.now().isoformat())
            )
            conn.execute(
                'INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)',
                ('last_accessed_path', lesson_path)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def apply_progress_to_tree(course: Course):
        """Apply saved progress to the course tree"""
        progress = ProgressTracker.load_progress(course)

        def apply_to_node(node: DirectoryNode):
            for lesson in node.lessons:
                lesson_path = os.path.relpath(lesson.path, course.path)
                lesson_path = lesson_path.replace('\\', '/')
                if lesson_path.startswith('/'):
                    lesson_path = lesson_path[1:]

                data = progress.get(lesson_path)
                if data:
                    lesson.completed = data.get('completed', False)
                    lesson.last_accessed = data.get('last_accessed')
                    lesson.progress_seconds = data.get('progress_seconds', 0)

            for child in node.children.values():
                apply_to_node(child)

        apply_to_node(course.root_node)
        course.last_accessed_path = progress.get('last_accessed_path')

    @staticmethod
    def get_completion_stats(course: Course) -> Dict[str, Any]:
        """Calculate completion statistics"""
        return DynamicCourseParser._calculate_completion_stats(course.root_node)


# Global course storage
current_course = None


@app.route('/')
def index():
    """Main dashboard"""
    global current_course

    if current_course is None:
        return render_template('course_dashboard.html',
                               course=None,
                               stats={'total_lessons': 0, 'completed_lessons': 0, 'completion_percentage': 0})

    ProgressTracker.apply_progress_to_tree(current_course)
    stats = ProgressTracker.get_completion_stats(current_course)
    logger.info(f"Dashboard: {stats}")

    return render_template('course_dashboard.html',
                           course=current_course,
                           stats=stats)


@app.route('/browse')
def browse_directories():
    """Browse directories for course selection"""
    path = request.args.get('path', '')
    
    try:
        # If no path specified, start with available drives on Windows
        if not path:
            import platform
            if platform.system() == 'Windows':
                # Get available drives on Windows
                import string
                drives = []
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if os.path.exists(drive):
                        drives.append({
                            'name': f"Drive {letter}:",
                            'path': drive,
                            'media_files': 0,
                            'is_course_candidate': False
                        })
                print(f"Returning {len(drives)} drives")
                return jsonify({
                    'current_path': 'Select a Drive',
                    'parent_path': None,
                    'directories': drives
                })
            else:
                # On other systems, start from home directory
                path = str(Path.home())

        current_path = Path(path)
        if not current_path.exists() or not current_path.is_dir():
            # Fallback to home directory if path doesn't exist
            current_path = Path.home()

        print(f"Browsing directory: {current_path}")

        # Get directories and basic info
        directories = []
        try:
            for item in sorted(current_path.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    try:
                        # Check if this looks like a course directory
                        media_count = len([f for f in item.rglob('*')
                                           if f.suffix.lower() in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS])

                        directories.append({
                            'name': item.name,
                            'path': str(item),
                            'media_files': media_count,
                            'is_course_candidate': media_count > 0
                        })
                    except (PermissionError, OSError):
                        directories.append({
                            'name': item.name + " (Access Denied)",
                            'path': str(item),
                            'media_files': 0,
                            'is_course_candidate': False
                        })
        except (PermissionError, OSError) as e:
            print(f"Access denied to {current_path}: {str(e)}")
            return jsonify({'error': f'Access denied to {current_path}: {str(e)}'}), 403

        # Determine parent path
        parent = None
        if current_path.parent != current_path:
            try:
                parent = str(current_path.parent)
            except (PermissionError, OSError):
                pass

        print(f"Found {len(directories)} directories")
        return jsonify({
            'current_path': str(current_path),
            'parent_path': parent,
            'directories': directories
        })

    except Exception as e:
        print(f"Error in browse_directories: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _search_folder_system_wide(folder_name: str) -> Optional[str]:
    """Search for a folder by name across the system.
    Uses mdfind (Spotlight) on macOS, find on Linux, or recursive walk as fallback.
    """
    import subprocess
    import platform

    system = platform.system()

    if system == 'Darwin':
        # macOS: use Spotlight (mdfind) — fast and searches everywhere
        try:
            # Simple text search via mdfind — no query syntax to break on special chars
            result = subprocess.run(
                ['mdfind', '-onlyin', os.path.expanduser('~'),
                 f"kMDItemKind == 'Folder' && kMDItemDisplayName == '{folder_name}'c"],
                capture_output=True, text=True, timeout=15
            )
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            for line in lines:
                if os.path.isdir(line) and os.path.basename(line) == folder_name:
                    logger.info(f"Found folder via Spotlight (home): {line}")
                    return line

            # Also try external volumes
            result = subprocess.run(
                ['mdfind', '-onlyin', '/Volumes',
                 f"kMDItemKind == 'Folder' && kMDItemDisplayName == '{folder_name}'c"],
                capture_output=True, text=True, timeout=10
            )
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            for line in lines:
                if os.path.isdir(line) and os.path.basename(line) == folder_name:
                    logger.info(f"Found folder via Spotlight (Volumes): {line}")
                    return line
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.warning(f"Spotlight search failed: {e}")

    # Fallback: use find (works on macOS and Linux)
    try:
        search_roots = [
            os.path.expanduser('~'),
        ]
        for root in search_roots:
            if not os.path.isdir(root):
                continue
            result = subprocess.run(
                ['find', root, '-maxdepth', '6', '-type', 'd',
                 '-name', folder_name, '-not', '-path', '*/\\.*', '-print', '-quit'],
                capture_output=True, text=True, timeout=30
            )
            line = result.stdout.strip()
            if line and os.path.isdir(line):
                logger.info(f"Found folder via find: {line}")
                return line
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning(f"find search failed: {e}")

    # Last resort: walk common directories (limited depth, breadth-first)
    search_roots = [
        os.path.expanduser('~/Downloads'),
        os.path.expanduser('~/Documents'),
        os.path.expanduser('~/Desktop'),
        os.path.expanduser('~/Courses'),
    ]
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        try:
            for entry in os.listdir(root):
                full = os.path.join(root, entry)
                if entry == folder_name and os.path.isdir(full):
                    logger.info(f"Found folder via walk: {full}")
                    return full
        except (PermissionError, OSError):
            continue

    return None


@app.route('/load_course', methods=['POST'])
def load_course():
    """Load course from selected directory"""
    global current_course

    data = request.json
    course_path = data.get('course_path')

    if not course_path:
        return jsonify({'error': 'Course path is required'}), 400

    logger.info(f"Attempting to load course from: {course_path!r}")

    # If it's not an absolute path or doesn't exist, try to find it
    if not os.path.exists(course_path):
        # Try to find the folder in common locations
        common_paths = [
            course_path,  # Try as-is first
            os.path.expanduser(f"~/{course_path}"),  # Home directory
            os.path.expanduser(f"~/Downloads/{course_path}"),  # Downloads
            os.path.expanduser(f"~/Documents/{course_path}"),  # Documents
            os.path.expanduser(f"~/Desktop/{course_path}"),  # Desktop
            os.path.expanduser(f"~/Courses/{course_path}"),  # Courses folder
            f"/Volumes/{course_path}",  # External drives (Mac)
        ]
        
        found_path = None
        for path in common_paths:
            if os.path.exists(path) and os.path.isdir(path):
                found_path = path
                break
        
        # If still not found, try system-wide search
        if not found_path:
            logger.info(f"Not found in common paths, trying system-wide search for: {course_path!r}")
            found_path = _search_folder_system_wide(course_path)

        if not found_path:
            return jsonify({
                'error': f'Course folder not found: "{course_path}". Try providing the full absolute path (e.g., /Users/username/Downloads/{course_path}).',
                'searched_locations': common_paths[:3]
            }), 400
        
        course_path = found_path
        logger.info(f"Resolved course path to: {course_path}")

    try:
        current_course = DynamicCourseParser.scan_directory(course_path)
        return jsonify({'success': True, 'course_name': current_course.name})
    except Exception as e:
        print(f"Error scanning course at {course_path}: {e}")
        return jsonify({'error': f'Failed to load course: {str(e)}'}), 500


@app.route('/api/file-dialog', methods=['POST'])
def open_file_dialog():
    """Open native file dialog to select course directory - falls back to web-based picker"""
    # Native file dialogs require GUI environment and tkinter, which may not be available
    # in server environments. Return info to use web-based file picker instead.
    return jsonify({
        'success': False,
        'available': False,
        'message': 'Using web-based file picker. Native dialogs are not available in this environment.'
    }), 200


@app.route('/lesson/<path:lesson_path>')
def view_lesson(lesson_path: str):
    """View specific lesson by path"""
    global current_course

    if not current_course:
        return redirect(url_for('index'))

    # Find the lesson in the tree
    lesson = find_lesson_in_tree(current_course.root_node, lesson_path)
    
    if not lesson:
        return redirect(url_for('index'))

    # Get all lessons for navigation
    all_lessons = get_all_lessons(current_course.root_node)
    current_index = -1
    
    # Find current lesson index
    for i, (path, lesson_obj) in enumerate(all_lessons):
        if lesson_obj == lesson:
            current_index = i
            break
    
    # Get next and previous lessons
    prev_lesson = None
    next_lesson = None
    
    if current_index > 0:
        prev_lesson = all_lessons[current_index - 1][0]
    
    if current_index < len(all_lessons) - 1:
        next_lesson = all_lessons[current_index + 1][0]

    # Convert lesson.path to the progress-tracking format (relative path from course root)
    progress_lesson_path = os.path.relpath(lesson.path, current_course.path)
    progress_lesson_path = progress_lesson_path.replace('\\', '/')
    if progress_lesson_path.startswith('/'):
        progress_lesson_path = progress_lesson_path[1:]

    # Update last accessed (preserve existing completion status)
    existing_progress = ProgressTracker.load_progress(current_course)
    existing_lesson = existing_progress.get(progress_lesson_path, {})
    was_completed = existing_lesson.get('completed', False)
    existing_seconds = existing_lesson.get('progress_seconds', 0)
    ProgressTracker.update_lesson_progress(
        current_course, progress_lesson_path,
        completed=was_completed,
        progress_seconds=existing_seconds
    )

    return render_template('lesson_view.html',
                           course=current_course,
                           lesson=lesson,
                           lesson_path=progress_lesson_path,
                           prev_lesson=prev_lesson,
                           next_lesson=next_lesson)


def get_lesson_url(lesson: Lesson, course_path: str) -> str:
    """Generate the URL for a lesson"""
    # Create relative path from course root
    lesson_file_path = os.path.relpath(lesson.path, course_path)
    lesson_file_path = lesson_file_path.replace('\\', '/')
    if lesson_file_path.startswith('/'):
        lesson_file_path = lesson_file_path[1:]
    
    # Append lesson title for uniqueness
    lesson_url = f"{lesson_file_path}/{lesson.title.replace(' ', '_')}"
    return lesson_url


def find_lesson_in_tree(node: DirectoryNode, target_path: str) -> Optional[Lesson]:
    """Find a lesson in the tree by path"""
    # Check lessons in current node
    for lesson in node.lessons:
        lesson_url = get_lesson_url(lesson, current_course.path)
        
        # Check multiple possible path formats
        lesson_file_path = os.path.relpath(lesson.path, current_course.path)
        lesson_file_path = lesson_file_path.replace('\\', '/')
        if lesson_file_path.startswith('/'):
            lesson_file_path = lesson_file_path[1:]
        
        # Also check with lesson title appended
        lesson_path_with_title = f"{lesson_file_path}/{lesson.title.replace(' ', '_')}"
        
        if (lesson_url == target_path or 
            lesson_file_path == target_path or 
            lesson_path_with_title == target_path):
            return lesson
    
    # Recursively search children
    for child in node.children.values():
        result = find_lesson_in_tree(child, target_path)
        if result:
            return result
    
    return None


def get_all_lessons(node: DirectoryNode) -> List[Tuple[str, Lesson]]:
    """Get all lessons from the tree with their paths"""
    lessons = []
    
    def collect_lessons(n: DirectoryNode, current_path: str = ""):
        # Add lessons from this node
        for lesson in n.lessons:
            lesson_url = get_lesson_url(lesson, current_course.path)
            lessons.append((lesson_url, lesson))
        
        # Recursively collect from children
        for child in n.children.values():
            collect_lessons(child, current_path)
    
    collect_lessons(node)
    return lessons


@app.route('/api/progress', methods=['POST'])
def update_progress():
    """API endpoint to update lesson progress"""
    global current_course

    if not current_course:
        return jsonify({'error': 'No course loaded'}), 400

    data = request.json
    lesson_path = data.get('lesson_path')
    completed = data.get('completed', False)
    progress_seconds = data.get('progress_seconds', 0)

    if not lesson_path:
        return jsonify({'error': 'lesson_path is required'}), 400

    try:
        ProgressTracker.update_lesson_progress(
            current_course, lesson_path, completed, progress_seconds
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating progress: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/files/<path:filepath>')
def serve_file(filepath):
    """Serve course files"""
    global current_course

    if not current_course:
        return "No course loaded", 404

    # Security: ensure file is within course directory
    try:
        # URL decode the filepath and normalize it
        from urllib.parse import unquote
        decoded_filepath = unquote(filepath)

        # Construct the full path relative to the course directory
        full_path = os.path.join(current_course.path, decoded_filepath)
        full_path = os.path.abspath(full_path)
        course_path = os.path.abspath(current_course.path)

        # Security check: ensure file is within course directory
        if not full_path.startswith(course_path):
            logger.warning(f"Access denied: {full_path} not in {course_path}")
            return "Access denied", 403

        if not os.path.exists(full_path):
            logger.warning(f"File not found: {full_path}")
            return "File not found", 404

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(full_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        return send_file(full_path, mimetype=mime_type)
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        return f"Error serving file: {str(e)}", 500

@app.route('/health')
def healthcheck():
    """Healthcheck endpoint for Docker"""
    return jsonify({"status": "healthy"}), 200

@app.route('/reset_course')
def reset_course():
    """Reset current course selection"""
    global current_course
    current_course = None
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# AI configuration helpers
# ---------------------------------------------------------------------------

_AI_CONFIG_FILE = Path('data/ai_config.json')


def _load_ai_config() -> Dict[str, Any]:
    try:
        if _AI_CONFIG_FILE.exists():
            return json.loads(_AI_CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {'provider': '', 'model': '', 'api_key': '', 'base_url': ''}


def _save_ai_config(config: Dict[str, Any]) -> None:
    _AI_CONFIG_FILE.parent.mkdir(exist_ok=True)
    _AI_CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding='utf-8')


# ---------------------------------------------------------------------------
# AI routes
# ---------------------------------------------------------------------------

@app.route('/api/ai/providers', methods=['GET'])
def get_ai_providers():
    """Return the catalogue of supported AI providers and their models."""
    return jsonify(AI_PROVIDERS)


@app.route('/api/ai/config', methods=['GET'])
def get_ai_config():
    """Return current AI configuration (API key masked)."""
    config = _load_ai_config()
    safe = dict(config)
    if safe.get('api_key'):
        safe['api_key'] = '***'
        safe['api_key_set'] = True
    else:
        safe['api_key_set'] = False
    return jsonify(safe)


@app.route('/api/ai/config', methods=['POST'])
def update_ai_config():
    """Save AI provider/model configuration."""
    data = request.json or {}
    config = _load_ai_config()
    for field in ('provider', 'model', 'base_url'):
        if field in data:
            config[field] = data[field]
    # Only update api_key when a real (non-masked) value is provided
    new_key = data.get('api_key', '')
    if new_key and new_key != '***':
        config['api_key'] = new_key
    _save_ai_config(config)
    return jsonify({'success': True})


@app.route('/api/ai/analyze', methods=['POST'])
def analyze_lesson_ai():
    """Trigger AI analysis for a lesson and persist the result."""
    global current_course

    if not current_course:
        return jsonify({'error': 'No course loaded'}), 400

    data = request.json or {}
    lesson_path = data.get('lesson_path', '').strip()
    if not lesson_path:
        return jsonify({'error': 'lesson_path is required'}), 400

    lesson = find_lesson_in_tree(current_course.root_node, lesson_path)
    if not lesson:
        return jsonify({'error': 'Lesson not found'}), 404

    config = _load_ai_config()
    if not config.get('provider') or not config.get('model'):
        return jsonify({
            'error': 'AI provider and model are not configured. '
                     'Open AI Settings and choose a provider + model.'
        }), 400

    try:
        analyzer = AIAnalyzer(config)
        analysis = analyzer.analyze_lesson(lesson, current_course.path)
        canonical = os.path.relpath(lesson.path, current_course.path).replace('\\', '/')
        AIAnalyzer.save_analysis(current_course.path, canonical, analysis)
        logger.info(f"AI analysis saved for: {canonical}")
        return jsonify({'success': True, 'analysis': analysis})
    except (ImportError, ValueError) as exc:
        logger.warning(f"AI config error: {exc}")
        return jsonify({'error': str(exc)}), 400
    except (ConnectionError, PermissionError, RuntimeError) as exc:
        logger.warning(f"AI provider error: {exc}")
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.error(f"AI analysis unexpected error: {exc}", exc_info=True)
        return jsonify({'error': f"Unexpected error: {exc}"}), 500


@app.route('/api/ai/analysis', methods=['GET'])
def get_lesson_analysis():
    """Return a previously stored AI analysis for a lesson."""
    global current_course

    if not current_course:
        return jsonify({'error': 'No course loaded'}), 400

    lesson_path = request.args.get('lesson_path', '').strip()
    if not lesson_path:
        return jsonify({'error': 'lesson_path is required'}), 400

    analysis = AIAnalyzer.load_analysis(current_course.path, lesson_path)
    if analysis:
        return jsonify({'success': True, 'analysis': analysis})
    return jsonify({'success': False, 'analysis': None})


def create_templates():
    """Create basic template files if they don't exist"""
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)

    # Basic select course template
    select_template = '''<!DOCTYPE html>
<html>
<head>
    <title>OfflineU - Select Course</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .directory { padding: 10px; border: 1px solid #ddd; margin: 5px 0; cursor: pointer; }
        .directory:hover { background-color: #f0f0f0; }
        .course-candidate { background-color: #e8f5e8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>OfflineU - Course Selection</h1>
        <div id="browser"></div>
        <script>
            // Basic directory browser implementation
            function loadDirectories(path = '') {
                fetch(`/browse?path=${encodeURIComponent(path)}`)
                    .then(r => r.json())
                    .then(data => {
                        const browser = document.getElementById('browser');
                        browser.innerHTML = `
                            <h3>Current: ${data.current_path}</h3>
                            ${data.parent_path ? `<div class="directory" onclick="loadDirectories('${data.parent_path}')">📁 .. (Parent)</div>` : ''}
                            ${data.directories.map(dir => `
                                <div class="directory ${dir.is_course_candidate ? 'course-candidate' : ''}" 
                                     onclick="${dir.is_course_candidate ? `loadCourse('${dir.path}')` : `loadDirectories('${dir.path}')`}">
                                    📁 ${dir.name} ${dir.media_files > 0 ? `(${dir.media_files} media files)` : ''}
                                </div>
                            `).join('')}
                        `;
                    });
            }

            function loadCourse(path) {
                fetch('/load_course', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({course_path: path})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('Error: ' + data.error);
                    }
                });
            }

            loadDirectories();
        </script>
    </div>
</body>
</html>'''

    # Basic course dashboard template
    dashboard_template = '''<!DOCTYPE html>
<html>
<head>
    <title>OfflineU - {{ course.name }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .module { margin: 20px 0; border: 1px solid #ddd; padding: 15px; }
        .lesson { padding: 8px; margin: 5px 0; border-left: 4px solid #ddd; }
        .lesson.completed { border-left-color: #4CAF50; background-color: #f8fff8; }
        .lesson a { text-decoration: none; color: #333; }
        .lesson:hover { background-color: #f0f0f0; }
        .progress { background-color: #f0f0f0; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-bar { background-color: #4CAF50; height: 100%; transition: width 0.3s; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ course.name }}</h1>
        <div class="progress">
            <div class="progress-bar" style="width: {{ stats.completion_percentage }}%"></div>
        </div>
        <p>Progress: {{ stats.completed_lessons }}/{{ stats.total_lessons }} lessons ({{ stats.completion_percentage }}%)</p>

        {% for module_idx, module in course.modules|enumerate %}
        <div class="module">
            <h2>{{ module.title }}</h2>
            {% for lesson_idx, lesson in module.lessons|enumerate %}
            <div class="lesson {% if lesson.completed %}completed{% endif %}">
                <a href="/lesson/{{ module_idx }}/{{ lesson_idx }}">
                    {{ lesson.title }} 
                    <small>({{ lesson.lesson_type }})</small>
                    {% if lesson.completed %}✓{% endif %}
                </a>
            </div>
            {% endfor %}
        </div>
        {% endfor %}

        <p><a href="/reset_course">Select Different Course</a></p>
    </div>
</body>
</html>'''

    # Basic lesson view template
    lesson_template = '''<!DOCTYPE html>
<html>
<head>
    <title>{{ lesson.title }} - {{ course.name }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        video, audio { width: 100%; max-width: 800px; }
        .content { margin: 20px 0; }
        .navigation { margin: 20px 0; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; }
        .file-link { display: block; margin: 5px 0; padding: 5px; background: #f0f0f0; text-decoration: none; color: #333; }
        .file-link:hover { background: #e0e0e0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ lesson.title }}</h1>
        <div class="navigation">
            <a href="/">← Back to Course</a>
            <button onclick="markCompleted()">Mark as Completed</button>
        </div>

        <div class="content">
            {% if lesson.video_file %}
            <h3>Video</h3>
            <video controls preload="metadata" id="video-player">
                <source src="/files/{{ lesson.video_file }}" type="video/mp4">
                {% if lesson.subtitle_file %}
                <track kind="subtitles" src="/files/{{ lesson.subtitle_file }}" srclang="en" label="English">
                {% endif %}
                Your browser does not support the video tag.
            </video>
            {% endif %}

            {% if lesson.audio_file %}
            <h3>Audio</h3>
            <audio controls preload="metadata" id="audio-player">
                <source src="/files/{{ lesson.audio_file }}" type="audio/mp3">
                Your browser does not support the audio tag.
            </audio>
            {% endif %}

            {% if lesson.text_files %}
            <h3>Additional Resources</h3>
            {% for text_file in lesson.text_files %}
            <a href="/files/{{ text_file }}" class="file-link" target="_blank">
                📄 {{ text_file.split('/')[-1] }}
            </a>
            {% endfor %}
            {% endif %}
        </div>

        <script>
            function markCompleted() {
                const lessonPath = '{{ lesson_path }}';
                console.log('Marking lesson as completed:', lessonPath);
                
                fetch('/api/progress', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        lesson_path: lessonPath,
                        completed: true,
                        progress_seconds: getProgressSeconds()
                    })
                })
                .then(r => r.json())
                .then(data => {
                    console.log('Progress response:', data);
                    if (data.success) {
                        alert('✓ Lesson marked as completed!');
                        window.location.href = '/';
                    } else {
                        alert('Error: ' + (data.error || 'Failed to mark as completed'));
                    }
                })
                .catch(error => {
                    console.error('Error marking lesson as completed:', error);
                    alert('Error: ' + error.message);
                });
            }

            function getProgressSeconds() {
                const video = document.getElementById('video-player');
                const audio = document.getElementById('audio-player');
                if (video) return Math.floor(video.currentTime || 0);
                if (audio) return Math.floor(audio.currentTime || 0);
                return 0;
            }

            // Auto-save progress periodically
            setInterval(() => {
                const seconds = getProgressSeconds();
                if (seconds > 0) {
                    fetch('/api/progress', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            lesson_path: '{{ lesson_path }}',
                            completed: false,
                            progress_seconds: seconds
                        })
                    })
                    .catch(error => console.error('Auto-save error:', error));
                }
            }, 30000); // Save every 30 seconds
        </script>
    </div>
</body>
</html>'''

    # Write templates to files
    template_files = {
        'select_course.html': select_template,
        'course_dashboard.html': dashboard_template,
        'lesson_view.html': lesson_template
    }

    for filename, content in template_files.items():
        template_path = templates_dir / filename
        if not template_path.exists():
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Created template: {template_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OfflineU Course Viewer & Tracker')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--create-templates', action='store_true', help='Create basic templates')
    parser.add_argument('course_path', nargs='?', help='Path to course directory')

    args = parser.parse_args()

    # Create templates if requested
    if args.create_templates:
        create_templates()
        print("Templates created successfully!")
        if not args.course_path:
            sys.exit(0)

    # Auto-load course if provided
    if args.course_path or os.environ.get('AUTO_LOAD_COURSE'):
        course_path = args.course_path or os.environ.get('AUTO_LOAD_COURSE')

        if not os.path.exists(course_path):
            print(f"Error: Course path does not exist: {course_path}", file=sys.stderr)
            sys.exit(1)

        try:
            current_course = DynamicCourseParser.scan_directory(course_path)
            print(f"Auto-loaded course: {current_course.name}")
            print(f"Built dynamic directory tree with {len(current_course.root_node.children)} top-level items")
        except Exception as e:
            print(f"Error loading course: {e}", file=sys.stderr)
            if args.debug:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    # Create templates directory if it doesn't exist
    if not Path('templates').exists():
        print("Templates directory not found. Creating basic templates...")
        create_templates()

    print(f"Starting OfflineU on http://{args.host}:{args.port}")
    print("Use --create-templates to regenerate template files")

    try:
        app.run(debug=args.debug, host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\nShutting down OfflineU...")
    except Exception as e:
        print(f"Error starting server: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)
