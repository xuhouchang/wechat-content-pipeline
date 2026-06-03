#!/usr/bin/env python3
"""
Embed images into article Markdown at IMAGE placeholder positions.

Takes a Markdown article and an images/ directory.
Scans for <!-- IMAGE: N --> placeholders, finds corresponding images in order,
and replaces placeholders with ![alt](./images/xxx).

Example:
  <!-- IMAGE: 1 --> → ![决策路径图](./images/image-001.jpg)
  <!-- IMAGE: 2 --> → ![会议效率图](./images/image-002.jpeg)

Card images (card-*.png) are also inserted at their corresponding IMAGE positions.

Usage:
  python3 embed_images.py article.md images/ [--dry-run]
"""

import sys
import os
import re
import argparse
from pathlib import Path


def describe_image(filepath: str) -> str:
    """Generate a Chinese alt text from the filename (rule-based, no LLM)."""
    base = Path(filepath).stem
    name_map = {
        # Generic mappings
        "decision": "决策路径",
        "decision_path": "决策路径",
        "productivity": "效率提升",
        "productivity_meeting": "会议效率",
        "team": "团队协作",
        "team_unity": "团队凝聚力",
        "chess": "博弈与判断",
        "chess_judgment": "判断力博弈",
        "judgment": "判断力",
        "bottleneck": "瓶颈",
        "workflow": "工作流程",
        "process": "流程",
        "automation": "自动化",
        "collaboration": "人机协作",
        "ai": "人工智能",
        "robot": "机器人",
        "human": "人机协同",
        "data": "数据",
        "chart": "数据图表",
        "analysis": "数据分析",
    }
    
    # Try to match known name parts
    for key, cn in name_map.items():
        if key in base.lower():
            return cn
    
    # Fallback: extract number suffix
    num_match = re.search(r'(\d+)', base)
    if num_match:
        return f"配图{num_match.group(1)}"
    
    return "示意图"


def get_sorted_images(images_dir: str) -> list[str]:
    """Get image files sorted by their numeric suffix."""
    img_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    images = []
    
    for f in os.listdir(images_dir):
        ext = Path(f).suffix.lower()
        if ext in img_exts:
            images.append(f)
    
    # Sort: image-001 → image-xxx first, then card-xxx
    def sort_key(name):
        base = Path(name).stem
        # Extract number
        nums = re.findall(r'\d+', base)
        num = int(nums[0]) if nums else 9999
        # image- prefixed comes before card- prefixed
        if base.startswith("image") or base.startswith("Image"):
            prefix = 0
        elif base.startswith("card") or base.startswith("Card"):
            prefix = 1
        else:
            prefix = 2
        return (prefix, num, name)
    
    images.sort(key=sort_key)
    return images


def embed_images(article_path: str, images_dir: str, dry_run: bool = False) -> bool:
    """Embed images at IMAGE placeholder positions in the article."""
    if not os.path.isdir(images_dir):
        print(f"⚠️ Images directory not found: {images_dir}")
        return False
    
    with open(article_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    images = get_sorted_images(images_dir)
    print(f"Found {len(images)} images in {images_dir}")
    for img in images:
        size = os.path.getsize(os.path.join(images_dir, img))
        print(f"  {img} ({size/1024:.0f}KB)")
    
    # Skip if no images
    if not images:
        print("No images to embed.")
        return False
    
    # Find all IMAGE placeholders (both formats)
    # Format 1: <!-- IMAGE: N --> (legacy)
    placeholders = list(re.finditer(r'<!--\s*IMAGE\s*:\s*(\d+)\s*-->', content, re.IGNORECASE))
    
    # Format 2: ![desc](./images/image-NNN-xxx.jpeg) — LLM already wrote image refs
    existing_images = list(re.finditer(r'!\[([^\]]*)\]\(\./images/(image-\d{3})[^)]+\)', content))
    
    if existing_images:
        print(f"Found {len(existing_images)} images already in ![]() format — fixing filename alignment...")
        
        # Build index of actual images by number prefix
        actual_by_num = {}  # {3: 'image-003-pexels.jpeg'}
        for fname in images:
            nums = re.findall(r'\d+', fname)
            if nums:
                n = int(nums[0])
                if n not in actual_by_num:
                    actual_by_num[n] = fname
        
        modified = content
        replacements = 0
        for img_match in reversed(list(existing_images)):
            full_tag = img_match.group(0)
            alt_text = img_match.group(1)
            num_prefix = img_match.group(2)
            num = int(re.search(r'\d+', num_prefix).group())
            
            actual_file = actual_by_num.get(num)
            if actual_file:
                tag_filename = re.search(r'\./images/([^)]+)', full_tag).group(1)
                if tag_filename != actual_file:
                    # Check if actual file exists
                    actual_path = os.path.join(images_dir, actual_file)
                    if os.path.exists(actual_path):
                        new_tag = full_tag.replace(tag_filename, actual_file)
                        modified = modified.replace(full_tag, new_tag, 1)
                        print(f'  ✏️ {tag_filename} → {actual_file}')
                        replacements += 1
                    else:
                        print(f'  ⚠️ Actual file not found: {actual_file}, leaving as-is')
                else:
                    # Filename already correct
                    pass
            else:
                print(f'  ⚠️ No actual file for image-{num:03d}, leaving as-is')
        
        if replacements > 0:
            with open(article_path, "w", encoding="utf-8") as f:
                f.write(modified)
            print(f'  ✅ Fixed {replacements} mismatched image filenames')
        else:
            print(f'  ✅ All image filenames already aligned')
        
        return True
    
    if not placeholders:
        print("No image placeholders found in article.")
        print("Images will not be embedded.")
        return False
    
    print(f"\nFound {len(placeholders)} <!-- IMAGE: N --> placeholders (legacy format)")
    
    # Map: image-xxx files to IMAGE N positions
    # Simple rule: image-001 → IMAGE 1, image-002 → IMAGE 2, etc.
    # card-xxx files also follow the same number scheme
    
    # Build mapping from image files to their number
    image_index = {}  # {number: filename}
    card_index = {}   # {number: [card_filenames]}
    
    for fname in images:
        base = Path(fname).stem
        nums = re.findall(r'\d+', base)
        if not nums:
            continue
        num = int(nums[0])
        
        if base.startswith("card") or base.startswith("Card"):
            if num not in card_index:
                card_index[num] = []
            card_index[num].append(fname)
        else:
            # Only assign if not already set (first match wins)
            if num not in image_index:
                image_index[num] = fname
    
    # Process placeholders in reverse order (to maintain position offsets)
    modified = content
    replacements = 0
    
    for ph in reversed(placeholders):
        ph_num = int(ph.group(1))
        ph_text = ph.group(0)
        ph_pos = ph.start()
        
        # Decide what to insert at this position
        inserted = False
        
        # 1. Card images for this number (if any)
        if ph_num in card_index:
            for card_fname in card_index[ph_num]:
                alt = describe_image(card_fname)
                img_tag = f"\n![{alt}](./images/{card_fname})\n"
                modified = modified[:ph_pos] + img_tag + modified[ph_pos + len(ph_text):]
                replacements += 1
                inserted = True
                print(f"  Placed card {card_fname} at IMAGE {ph_num}")
        
        # 2. Real image for this number (if any and not already replaced)
        if ph_num in image_index and not inserted:
            img_fname = image_index[ph_num]
            alt = describe_image(img_fname)
            img_tag = f"\n![{alt}](./images/{img_fname})\n"
            modified = modified[:ph_pos] + img_tag + modified[ph_pos + len(ph_text):]
            replacements += 1
            print(f"  Placed image {img_fname} at IMAGE {ph_num}")
    
    if replacements == 0:
        print("\nWarning: No replacements were made. Removing all image placeholders from article.")
        # Strip all remaining IMAGE placeholders (both formats)
        modified = re.sub(r'<!--\s*IMAGE\s*:\s*\d+\s*-->\s*', '', modified, flags=re.IGNORECASE)
        modified = re.sub(r'!\[[^\]]*\]\(\.[^)]+\)\s*', '', modified)
        with open(article_path, "w", encoding="utf-8") as f:
            f.write(modified)
        print("  ✅ All image placeholders removed from article.")
        return True
    
    if dry_run:
        print(f"\n[Dry run] Would replace {replacements} placeholders in {article_path}")
        return True
    
    # Write back
    with open(article_path, "w", encoding="utf-8") as f:
        f.write(modified)
    
    print(f"\n✅ Replaced {replacements} placeholders in {article_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Embed images at IMAGE placeholders in Markdown articles")
    parser.add_argument("article", help="Path to Markdown article file")
    parser.add_argument("images_dir", help="Path to images directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without modifying")
    
    args = parser.parse_args()
    success = embed_images(args.article, args.images_dir, args.dry_run)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
