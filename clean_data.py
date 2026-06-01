#!/usr/bin/env python
"""
Data cleanup utility for Solar System Calculator.

Removes training data, models, and cache files to reset project state.
Useful for starting fresh or cleaning up before redistribution.
"""

import argparse
import shutil
from pathlib import Path


def clean_observations(dry_run: bool = False) -> None:
    """Remove observations.csv file."""
    path = Path("observations.csv")
    if path.exists():
        if dry_run:
            print(f"  [DRY RUN] Would delete: {path}")
        else:
            path.unlink()
            print(f"  ✓ Deleted: {path}")
    else:
        print(f"  - Not found: {path}")


def clean_models(dry_run: bool = False) -> None:
    """Remove models directory and all trained models."""
    path = Path("models")
    if path.exists():
        if dry_run:
            models = list(path.glob("*.joblib"))
            print(f"  [DRY RUN] Would delete {len(models)} model files in {path}/")
            for model in models:
                print(f"           - {model.name}")
        else:
            count = len(list(path.glob("*.joblib")))
            shutil.rmtree(path)
            print(f"  ✓ Deleted: {path}/ ({count} models)")
    else:
        print(f"  - Not found: {path}/")


def clean_cache(dry_run: bool = False) -> None:
    """Remove Python cache files."""
    cache_dirs = [
        Path("__pycache__"),
        Path("solarsystemcalculator/__pycache__"),
    ]
    
    total_files = 0
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            files = list(cache_dir.glob("**/*.pyc")) + list(cache_dir.glob("**/__pycache__"))
            total_files += len(files)
            
            if dry_run:
                print(f"  [DRY RUN] Would delete: {cache_dir}/ ({len(files)} files)")
            else:
                shutil.rmtree(cache_dir)
                print(f"  ✓ Deleted: {cache_dir}/")
    
    if total_files == 0 and not dry_run:
        print(f"  - No cache files found")


def clean_egg_info(dry_run: bool = False) -> None:
    """Remove .egg-info directory."""
    path = Path("solarsystemcalculator.egg-info")
    if path.exists():
        if dry_run:
            files = list(path.glob("**/*"))
            print(f"  [DRY RUN] Would delete: {path}/ ({len(files)} files)")
        else:
            shutil.rmtree(path)
            print(f"  ✓ Deleted: {path}/")
    else:
        print(f"  - Not found: {path}/")


def clean_build(dry_run: bool = False) -> None:
    """Remove build directory."""
    path = Path("build")
    if path.exists():
        if dry_run:
            files = list(path.glob("**/*"))
            print(f"  [DRY RUN] Would delete: {path}/ ({len(files)} files)")
        else:
            shutil.rmtree(path)
            print(f"  ✓ Deleted: {path}/")
    else:
        print(f"  - Not found: {path}/")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up data, models, and cache files to reset project state."
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Remove observations, models, cache, and build files (full clean)",
    )
    parser.add_argument(
        "--observations",
        action="store_true",
        help="Remove observations.csv only",
    )
    parser.add_argument(
        "--models",
        action="store_true",
        help="Remove trained models only",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Remove Python cache files only",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Remove build artifacts",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    
    args = parser.parse_args()
    
    # If nothing specified, show help
    if not any([args.all, args.observations, args.models, args.cache, args.build]):
        parser.print_help()
        return 0
    
    print("🧹 Solar System Calculator - Data Cleanup")
    print("=" * 50)
    
    if args.dry_run:
        print("\n[DRY RUN MODE] - No files will be deleted\n")
    
    if args.all:
        print("\nCleaning everything:")
        clean_observations(args.dry_run)
        clean_models(args.dry_run)
        clean_cache(args.dry_run)
        clean_build(args.dry_run)
        clean_egg_info(args.dry_run)
    else:
        if args.observations:
            print("\nCleaning observations:")
            clean_observations(args.dry_run)
        
        if args.models:
            print("\nCleaning models:")
            clean_models(args.dry_run)
        
        if args.cache:
            print("\nCleaning cache:")
            clean_cache(args.dry_run)
        
        if args.build:
            print("\nCleaning build:")
            clean_build(args.dry_run)
    
    print("\n" + "=" * 50)
    
    if args.dry_run:
        print("✓ Dry run complete - no files were deleted")
        print("\nRun without --dry-run to actually delete files")
    else:
        print("✓ Cleanup complete!")
        print("\nTo start fresh:")
        print("  python generate_observations.py --count 128")
        print("  python self_improve.py observations.csv")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
