"""Backup and cleanup jobs for data management."""

from pathlib import Path
from datetime import datetime, timedelta
import json
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BackupManager:
    """Manage project backups and archival."""

    def __init__(self, storage_root: Path = Path("storage")):
        """Initialize backup manager."""
        self.storage_root = storage_root
        self.backup_dir = storage_root / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_project_backup(self, project_id: str, include_vectors: bool = False) -> Path:
        """
        Create a backup of a project.

        Args:
            project_id: Project ID to backup
            include_vectors: Whether to include vector data

        Returns:
            Path to backup archive
        """
        project_dir = self.storage_root / "projects" / project_id
        
        if not project_dir.exists():
            raise ValueError(f"Project {project_id} not found")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{project_id}_backup_{timestamp}"
        backup_path = self.backup_dir / backup_name

        # Create backup structure
        backup_path.mkdir(parents=True, exist_ok=True)

        # Copy project data, excluding vectors if requested
        for item in project_dir.iterdir():
            if not include_vectors and item.name == "vectors":
                continue
            
            if item.is_dir():
                shutil.copytree(item, backup_path / item.name)
            else:
                shutil.copy2(item, backup_path)

        # Create backup metadata
        metadata = {
            "project_id": project_id,
            "backup_date": datetime.now().isoformat(),
            "include_vectors": include_vectors,
            "size_mb": sum(f.stat().st_size for f in backup_path.rglob("*")) / (1024 * 1024),
        }
        
        metadata_file = backup_path / "backup_metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))

        logger.info(f"Created backup: {backup_path}")
        return backup_path

    def restore_project_backup(self, project_id: str, backup_path: Path) -> bool:
        """
        Restore a project from backup.

        Args:
            project_id: Project ID to restore to
            backup_path: Path to backup directory

        Returns:
            True if successful
        """
        if not backup_path.exists():
            raise ValueError(f"Backup not found: {backup_path}")

        project_dir = self.storage_root / "projects" / project_id

        # Create a safety backup of current project
        if project_dir.exists():
            self.create_project_backup(project_id)

        # Clear and restore
        if project_dir.exists():
            shutil.rmtree(project_dir)

        shutil.copytree(backup_path, project_dir)
        
        logger.info(f"Restored project {project_id} from {backup_path}")
        return True

    def list_backups(self, project_id: Optional[str] = None) -> list[dict]:
        """
        List available backups.

        Args:
            project_id: Filter by project ID (optional)

        Returns:
            List of backup metadata
        """
        backups = []
        
        for backup_path in self.backup_dir.iterdir():
            if not backup_path.is_dir():
                continue
            
            metadata_file = backup_path / "backup_metadata.json"
            if not metadata_file.exists():
                continue

            metadata = json.loads(metadata_file.read_text())
            
            if project_id and metadata["project_id"] != project_id:
                continue
            
            metadata["backup_path"] = str(backup_path)
            backups.append(metadata)
        
        return sorted(backups, key=lambda x: x["backup_date"], reverse=True)


class CleanupManager:
    """Manage cleanup and archival of old data."""

    def __init__(self, storage_root: Path = Path("storage")):
        """Initialize cleanup manager."""
        self.storage_root = storage_root

    def cleanup_old_runs(self, project_id: str, days: int = 30, dry_run: bool = True) -> list[str]:
        """
        Clean up old generation runs.

        Args:
            project_id: Project ID
            days: Delete runs older than this many days
            dry_run: If True, only report what would be deleted

        Returns:
            List of deleted/to-be-deleted paths
        """
        deleted = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        runs_dir = self.storage_root / "projects" / project_id / "runs"
        if not runs_dir.exists():
            return deleted

        for run_file in runs_dir.iterdir():
            if not run_file.is_file():
                continue

            file_time = datetime.fromtimestamp(run_file.stat().st_mtime)
            if file_time < cutoff_date:
                if not dry_run:
                    run_file.unlink()
                deleted.append(str(run_file))

        logger.info(f"Cleanup: Found {len(deleted)} old runs for {project_id}")
        return deleted

    def cleanup_cache(self, dry_run: bool = True) -> list[str]:
        """
        Clean up cache directory.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            List of deleted/to-be-deleted paths
        """
        deleted = []
        cache_dir = self.storage_root / "cache"
        
        if not cache_dir.exists():
            return deleted

        for item in cache_dir.rglob("*"):
            if item.is_file():
                # Clean up files older than 7 days
                file_time = datetime.fromtimestamp(item.stat().st_mtime)
                cutoff = datetime.now() - timedelta(days=7)
                
                if file_time < cutoff:
                    if not dry_run:
                        item.unlink()
                    deleted.append(str(item))

        logger.info(f"Cleanup: Found {len(deleted)} cache files to delete")
        return deleted

    def cleanup_orphaned_vectors(self, dry_run: bool = True) -> list[str]:
        """
        Clean up vector entries for deleted documents.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            List of deleted/to-be-deleted vectors
        """
        deleted = []
        vectors_dir = self.storage_root / "vectors"
        
        if not vectors_dir.exists():
            return deleted

        # Get all document IDs
        valid_docs = set()
        projects_dir = self.storage_root / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                parsed_dir = project_dir / "parsed"
                if parsed_dir.exists():
                    for doc_file in parsed_dir.glob("*.json"):
                        valid_docs.add(doc_file.stem)

        # Find and delete orphaned vectors
        for vector_file in vectors_dir.glob("*.json"):
            doc_id = vector_file.stem
            if doc_id not in valid_docs:
                if not dry_run:
                    vector_file.unlink()
                deleted.append(str(vector_file))

        logger.info(f"Cleanup: Found {len(deleted)} orphaned vector files")
        return deleted

    def archive_project(self, project_id: str, backup_first: bool = True) -> Path:
        """
        Archive a completed project.

        Args:
            project_id: Project to archive
            backup_first: Create backup before archiving

        Returns:
            Path to archive file
        """
        project_dir = self.storage_root / "projects" / project_id
        if not project_dir.exists():
            raise ValueError(f"Project {project_id} not found")

        # Create backup if requested
        if backup_first:
            backup_manager = BackupManager(self.storage_root)
            backup_manager.create_project_backup(project_id, include_vectors=True)

        # Create archive
        archive_dir = self.storage_root / "archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"{project_id}_archive_{timestamp}"

        shutil.make_archive(str(archive_path), "zip", project_dir)
        
        logger.info(f"Archived project {project_id} to {archive_path}.zip")
        return Path(f"{archive_path}.zip")

    def get_storage_stats(self) -> dict:
        """Get storage usage statistics."""
        stats = {
            "total_size_mb": 0,
            "projects": {},
            "backups_mb": 0,
            "cache_mb": 0,
            "vectors_mb": 0,
        }

        # Project sizes
        projects_dir = self.storage_root / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                size = sum(f.stat().st_size for f in project_dir.rglob("*")) / (1024 * 1024)
                stats["projects"][project_dir.name] = size
                stats["total_size_mb"] += size

        # Backup sizes
        backup_dir = self.storage_root / "backups"
        if backup_dir.exists():
            stats["backups_mb"] = sum(f.stat().st_size for f in backup_dir.rglob("*")) / (1024 * 1024)
            stats["total_size_mb"] += stats["backups_mb"]

        # Cache sizes
        cache_dir = self.storage_root / "cache"
        if cache_dir.exists():
            stats["cache_mb"] = sum(f.stat().st_size for f in cache_dir.rglob("*")) / (1024 * 1024)
            stats["total_size_mb"] += stats["cache_mb"]

        # Vector sizes
        vectors_dir = self.storage_root / "vectors"
        if vectors_dir.exists():
            stats["vectors_mb"] = sum(f.stat().st_size for f in vectors_dir.rglob("*")) / (1024 * 1024)
            stats["total_size_mb"] += stats["vectors_mb"]

        return stats
