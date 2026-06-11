"""CLI tools for backup and cleanup operations."""

import click
import json
from pathlib import Path
from datetime import datetime
from tabulate import tabulate

from backend.operations import BackupManager, CleanupManager


@click.group()
def cli():
    """Backup and cleanup management tools."""
    pass


@cli.group()
def backup():
    """Backup management commands."""
    pass


@backup.command()
@click.argument("project_id")
@click.option("--include-vectors", is_flag=True, help="Include vector data in backup")
@click.option("--storage", default="storage", help="Storage root directory")
def create(project_id: str, include_vectors: bool, storage: str):
    """Create a backup of a project."""
    manager = BackupManager(storage_root=Path(storage))
    
    try:
        backup_path = manager.create_project_backup(project_id, include_vectors=include_vectors)
        click.secho(f"✓ Backup created: {backup_path}", fg="green")
    except Exception as exc:
        click.secho(f"✗ Backup failed: {exc}", fg="red")


@backup.command()
@click.argument("project_id")
@click.argument("backup_path")
@click.option("--storage", default="storage", help="Storage root directory")
def restore(project_id: str, backup_path: str, storage: str):
    """Restore a project from backup."""
    manager = BackupManager(storage_root=Path(storage))
    
    try:
        manager.restore_project_backup(project_id, Path(backup_path))
        click.secho(f"✓ Project {project_id} restored from {backup_path}", fg="green")
    except Exception as exc:
        click.secho(f"✗ Restore failed: {exc}", fg="red")


@backup.command()
@click.option("--project", help="Filter by project ID")
@click.option("--storage", default="storage", help="Storage root directory")
def list_backups(project: str, storage: str):
    """List available backups."""
    manager = BackupManager(storage_root=Path(storage))
    
    backups = manager.list_backups(project_id=project)
    
    if not backups:
        click.echo("No backups found")
        return

    table_data = [
        [
            b["project_id"],
            b["backup_date"],
            f"{b['size_mb']:.2f} MB",
            "Yes" if b["include_vectors"] else "No",
        ]
        for b in backups
    ]

    headers = ["Project", "Date", "Size", "Includes Vectors"]
    click.echo(tabulate(table_data, headers=headers))


@cli.group()
def cleanup():
    """Cleanup and maintenance commands."""
    pass


@cleanup.command()
@click.argument("project_id")
@click.option("--days", default=30, help="Delete runs older than N days")
@click.option("--dry-run", is_flag=True, help="Preview what would be deleted")
@click.option("--storage", default="storage", help="Storage root directory")
def old_runs(project_id: str, days: int, dry_run: bool, storage: str):
    """Clean up old generation runs."""
    manager = CleanupManager(storage_root=Path(storage))
    
    deleted = manager.cleanup_old_runs(project_id, days=days, dry_run=dry_run)
    
    if deleted:
        action = "Would delete" if dry_run else "Deleted"
        click.secho(f"{action} {len(deleted)} old runs", fg="yellow")
        for path in deleted[:5]:
            click.echo(f"  - {path}")
        if len(deleted) > 5:
            click.echo(f"  ... and {len(deleted) - 5} more")
    else:
        click.echo("No old runs found")


@cleanup.command()
@click.option("--dry-run", is_flag=True, help="Preview what would be deleted")
@click.option("--storage", default="storage", help="Storage root directory")
def cache(dry_run: bool, storage: str):
    """Clean up cache directory."""
    manager = CleanupManager(storage_root=Path(storage))
    
    deleted = manager.cleanup_cache(dry_run=dry_run)
    
    if deleted:
        action = "Would delete" if dry_run else "Deleted"
        click.secho(f"{action} {len(deleted)} cache files", fg="yellow")
    else:
        click.echo("No cache files to clean")


@cleanup.command()
@click.option("--dry-run", is_flag=True, help="Preview what would be deleted")
@click.option("--storage", default="storage", help="Storage root directory")
def orphaned_vectors(dry_run: bool, storage: str):
    """Clean up orphaned vector files."""
    manager = CleanupManager(storage_root=Path(storage))
    
    deleted = manager.cleanup_orphaned_vectors(dry_run=dry_run)
    
    if deleted:
        action = "Would delete" if dry_run else "Deleted"
        click.secho(f"{action} {len(deleted)} orphaned vectors", fg="yellow")
    else:
        click.echo("No orphaned vectors found")


@cleanup.command()
@click.argument("project_id")
@click.option("--backup-first", is_flag=True, default=True, help="Create backup before archiving")
@click.option("--storage", default="storage", help="Storage root directory")
def archive(project_id: str, backup_first: bool, storage: str):
    """Archive a project."""
    manager = CleanupManager(storage_root=Path(storage))
    
    try:
        archive_path = manager.archive_project(project_id, backup_first=backup_first)
        click.secho(f"✓ Project archived to {archive_path}", fg="green")
    except Exception as exc:
        click.secho(f"✗ Archive failed: {exc}", fg="red")


@cleanup.command()
@click.option("--storage", default="storage", help="Storage root directory")
def stats(storage: str):
    """Show storage usage statistics."""
    manager = CleanupManager(storage_root=Path(storage))
    
    stats_data = manager.get_storage_stats()
    
    click.echo("Storage Usage Statistics")
    click.echo("=" * 50)
    click.echo(f"Total Size: {stats_data['total_size_mb']:.2f} MB")
    click.echo(f"Backups:    {stats_data['backups_mb']:.2f} MB")
    click.echo(f"Cache:      {stats_data['cache_mb']:.2f} MB")
    click.echo(f"Vectors:    {stats_data['vectors_mb']:.2f} MB")
    click.echo()
    
    if stats_data["projects"]:
        click.echo("Projects:")
        table_data = [[name, f"{size:.2f} MB"] for name, size in stats_data["projects"].items()]
        click.echo(tabulate(table_data, headers=["Project", "Size"]))


if __name__ == "__main__":
    cli()
