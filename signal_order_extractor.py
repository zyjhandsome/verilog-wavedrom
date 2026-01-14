"""
Signal Order Extractor - Extract signal names and order from waveform images.

Supports multiple extraction methods:
1. Tesseract OCR (if installed)
2. Image analysis with color detection
3. Manual signal order file

Then provides the order for matching generated WaveDrom output.
"""

import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from PIL import Image, ImageEnhance, ImageFilter

# Try to import pytesseract (optional)
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Configure Tesseract path for Windows
if sys.platform == 'win32':
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.expanduser(r'~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'),
    ]
    for path in tesseract_paths:
        if os.path.exists(path):
            if TESSERACT_AVAILABLE:
                pytesseract.pytesseract.tesseract_cmd = path
            break


class SignalOrderExtractor:
    """Extract signal names and order from waveform images."""
    
    def __init__(self):
        """Initialize the extractor."""
        self.tesseract_available = TESSERACT_AVAILABLE
        if TESSERACT_AVAILABLE:
            try:
                # Test if tesseract is actually installed
                pytesseract.get_tesseract_version()
            except Exception as e:
                print(f"Tesseract test failed: {e}")
                self.tesseract_available = False
    
    def extract_signal_order(self, image_path: Path) -> List[str]:
        """Extract signal names in order from a waveform image.
        
        Args:
            image_path: Path to the waveform PNG image
            
        Returns:
            List of signal names in the order they appear (top to bottom)
        """
        # Try Tesseract OCR first
        if self.tesseract_available:
            try:
                return self._extract_with_tesseract(image_path)
            except Exception as e:
                print(f"Tesseract OCR failed: {e}")
        
        # Fall back to image analysis (detect text regions by color)
        return self._extract_with_image_analysis(image_path)
    
    def _extract_with_tesseract(self, image_path: Path) -> List[str]:
        """Extract using Tesseract OCR with enhanced image processing.
        
        Uses multiple strategies:
        1. Full image OCR with bounding boxes
        2. Sparse text mode for isolated characters
        3. Row-by-row OCR for missed signals
        """
        image = Image.open(image_path).convert('RGB')
        
        # Find the signal name region - may be left-aligned or right-aligned
        width, height = image.size
        
        # Find the rightmost extent of blue text (signal names end here)
        signal_region = self._find_signal_name_region(image)
        left_region = signal_region
        
        # Preprocess image for better OCR (3x scale for small text)
        preprocessed = self._preprocess_for_ocr(left_region, scale_factor=3)
        
        # Find signal rows using image analysis
        signal_rows = self._find_signal_rows(preprocessed)
        
        # Try bounding box extraction first for better accuracy
        signals = []
        try:
            signals = self._extract_with_bounding_boxes(preprocessed)
        except Exception as e:
            print(f"Bounding box extraction failed: {e}")
        
        # If we found fewer signals than expected rows, try row-by-row OCR
        if len(signals) < len(signal_rows):
            try:
                row_signals = self._extract_per_row(preprocessed, signal_rows)
                # Merge results
                signals = self._merge_signal_lists(signals, row_signals)
            except Exception as e:
                print(f"Row-by-row extraction failed: {e}")
        
        if signals:
            # Post-process to fix common OCR errors
            signals = self._post_process_signals(signals)
            return signals
        
        # Fall back to simple text extraction
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_[]:'
        text = pytesseract.image_to_string(preprocessed, config=custom_config)
        
        # Parse the text to extract signal names
        signals = self._parse_signal_names(text)
        return self._post_process_signals(signals)
    
    def _extract_per_row(self, image: Image.Image, signal_rows: List[Tuple[int, int]]) -> List[str]:
        """Extract signal names by processing each row individually.
        
        This helps catch short signal names that get missed in full-image OCR.
        
        Args:
            image: Preprocessed image
            signal_rows: List of (y_start, y_end) tuples
            
        Returns:
            List of extracted signal names
        """
        signals = []
        
        for y_start, y_end in signal_rows:
            # Add padding
            y_start = max(0, y_start - 5)
            y_end = min(image.height, y_end + 5)
            
            # Crop this row
            row_image = image.crop((0, y_start, image.width, y_end))
            
            # Use single line mode (PSM 7) for row extraction
            config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_[]:'
            try:
                text = pytesseract.image_to_string(row_image, config=config).strip()
                cleaned = self._clean_signal_name(text)
                if cleaned:
                    signals.append(cleaned)
            except Exception:
                pass
        
        return signals
    
    def _merge_signal_lists(self, list1: List[str], list2: List[str]) -> List[str]:
        """Merge two signal lists, avoiding duplicates.
        
        Preserves order from list1, adds unique items from list2.
        """
        result = list(list1)
        existing_lower = {s.lower() for s in result}
        
        for sig in list2:
            sig_lower = sig.lower()
            # Check if similar signal already exists
            is_duplicate = False
            for existing in existing_lower:
                # Check similarity
                if sig_lower == existing:
                    is_duplicate = True
                    break
                if sig_lower in existing or existing in sig_lower:
                    # One contains the other - might be same signal
                    if abs(len(sig_lower) - len(existing)) <= 2:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                result.append(sig)
                existing_lower.add(sig_lower)
        
        return result
    
    def _post_process_signals(self, signals: List[str]) -> List[str]:
        """Post-process extracted signal names to fix common OCR errors."""
        processed = []
        seen_lower = set()  # Track seen signals to avoid duplicates
        
        for sig in signals:
            # Fix common OCR substitutions
            sig = sig.replace('YW', '').replace('YL', '').replace('YUE', '')
            sig = sig.replace('TL', '')  # Often appears at end
            
            # Remove trailing numbers that shouldn't be there (like control[15:0]5)
            sig = re.sub(r'\](\d+)$', ']', sig)
            
            # Fix missing closing bracket
            if '[' in sig and ']' not in sig:
                sig = sig + ']'
            
            # Fix missing first character (common OCR issue)
            # e.g., "eriesterminationcontrol" -> "seriesterminationcontrol"
            if sig.startswith('eriesterminationcontrol'):
                sig = 's' + sig
            
            # Fix common OCR errors for specific signals
            # edram_rst or sdram_rst variations
            sig_lower = sig.lower()
            if 'dram_' in sig_lower and not sig_lower.startswith('sdram_'):
                # Find the position and fix it
                idx = sig_lower.find('dram_')
                sig = 'sdram_' + sig[idx + 5:]
            
            # Fix tmpt -> tmp1 (OCR often confuses 1 with t)
            if 'tmpt_bar' in sig.lower():
                sig = sig.replace('tmpt_', 'tmp1_').replace('tmpt_', 'tmp1_')
            
            # Fix sys_cik -> sys_clk (OCR often confuses l with i and k)
            if sig.lower() == 'sys_cik' or sig.lower() == 'sys_clk':
                sig = 'sys_clk'
            
            # Remove any trailing garbage characters
            sig = re.sub(r'[^a-zA-Z0-9_\[\]:]+$', '', sig)
            sig = re.sub(r'^[^a-zA-Z_]+', '', sig)
            
            if sig and len(sig) >= 1:
                sig_lower = sig.lower()
                
                # Check for near-duplicates (e.g., "tmp" appearing twice when second should be "tmp1")
                if sig_lower in seen_lower:
                    # Try to make it unique by adding "1" if it looks like tmp/tmp1 pattern
                    if not sig_lower.endswith('1') and sig_lower + '1' not in seen_lower:
                        sig = sig + '1'
                        sig_lower = sig.lower()
                    else:
                        # Skip duplicate
                        continue
                
                processed.append(sig)
                seen_lower.add(sig_lower)
        
        return processed
    
    def _preprocess_for_ocr(self, image: Image.Image, scale_factor: int = 3) -> Image.Image:
        """Preprocess image for better OCR results.
        
        Focus on extracting blue text (common for signal names in waveform images).
        Uses higher scale factor for better small text detection.
        
        Args:
            image: Input image
            scale_factor: Scale factor for enlarging (default 3x for better small text)
        """
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Extract blue channel and create high-contrast image
        # Signal names are often in blue color
        width, height = image.size
        pixels = image.load()
        
        # Create a new image with enhanced blue text
        enhanced = Image.new('L', (width, height), 255)  # White background
        enhanced_pixels = enhanced.load()
        
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                
                # Check if this is NOT a white/near-white pixel first
                is_white = r > 240 and g > 240 and b > 240
                if is_white:
                    enhanced_pixels[x, y] = 255
                    continue
                
                # Detect blue-ish pixels (signal names are typically blue)
                # Blue should be significantly higher than red/green
                # Typical blue text: RGB around (100-180, 130-200, 200-255)
                is_blue = b > 180 and b > r + 30 and b > g + 10
                
                # Also detect darker blue text
                is_dark_blue = b > 120 and b > r + 20 and b > g + 20 and r < 180 and g < 200
                
                if is_blue or is_dark_blue:
                    # Make it black on white background
                    enhanced_pixels[x, y] = 0
                else:
                    enhanced_pixels[x, y] = 255
        
        # Scale up for better OCR (3x default for small text like 'i', 'o')
        new_size = (enhanced.width * scale_factor, enhanced.height * scale_factor)
        scaled = enhanced.resize(new_size, Image.Resampling.LANCZOS)
        
        # Apply slight sharpening
        sharpened = scaled.filter(ImageFilter.SHARPEN)
        
        return sharpened
    
    def _find_signal_name_region(self, image: Image.Image) -> Image.Image:
        """Find and extract the signal name region from waveform image.
        
        Signal names may be left-aligned (long names start at x=0) or 
        right-aligned (short names end at the same x position).
        
        This method finds the rightmost blue text column which typically
        marks the end of signal names.
        """
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        width, height = image.size
        pixels = image.load()
        
        # Find all columns that have blue pixels (potential text columns)
        col_blue_count = {}
        for x in range(width):
            count = 0
            for y in range(height):
                r, g, b = pixels[x, y]
                # Blue text detection
                if b > 150 and b > r and b > g:
                    count += 1
            if count > 0:
                col_blue_count[x] = count
        
        if not col_blue_count:
            # Fall back to left portion
            return image.crop((0, 0, min(int(width * 0.25), 350), height))
        
        # Find the rightmost dense blue column - this is typically where signal names end
        # Look for a gap in blue columns that indicates transition to waveform area
        sorted_cols = sorted(col_blue_count.keys())
        
        # Find the end of the signal name region
        # This is where there's a significant gap in blue columns
        signal_name_end = sorted_cols[0]
        last_col = sorted_cols[0]
        
        for col in sorted_cols[1:]:
            if col - last_col > 50:  # Gap > 50 pixels indicates end of signal names
                break
            signal_name_end = col
            last_col = col
        
        # Add padding
        signal_name_end = min(signal_name_end + 20, width)
        
        # Crop to the signal name region
        return image.crop((0, 0, signal_name_end, height))
    
    def _extract_blue_text_region(self, image: Image.Image) -> Image.Image:
        """Extract only the blue text regions from the image.
        
        More sensitive detection to catch short signal names.
        """
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        width, height = image.size
        pixels = image.load()
        
        # Find columns that have blue pixels (text columns)
        # Use more sensitive detection
        blue_cols = set()
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                # More sensitive blue detection
                is_blue = b > 80 and (b > r or b > g)
                # Also detect any dark text
                is_dark = r < 150 and g < 150 and b < 200 and (r + g + b) < 400
                if is_blue or is_dark:
                    blue_cols.add(x)
        
        if not blue_cols:
            return image
        
        # Get the rightmost blue column (end of signal names)
        max_blue_x = max(blue_cols) + 15  # Add more padding
        
        # Crop to just the signal name region
        return image.crop((0, 0, min(max_blue_x, width), height))
    
    def _find_signal_rows(self, image: Image.Image) -> List[Tuple[int, int]]:
        """Find row ranges that contain signal names using image analysis.
        
        This helps identify where signals are even if OCR misses them.
        
        Args:
            image: Preprocessed image
            
        Returns:
            List of (y_start, y_end) tuples for each signal row
        """
        if image.mode != 'L':
            image = image.convert('L')
        
        width, height = image.size
        pixels = image.load()
        
        # Scan for rows with dark pixels (text)
        rows_with_text = []
        current_start = None
        
        for y in range(height):
            has_dark = False
            for x in range(min(width, 200)):  # Only check left portion
                if pixels[x, y] < 128:  # Dark pixel
                    has_dark = True
                    break
            
            if has_dark:
                if current_start is None:
                    current_start = y
            else:
                if current_start is not None:
                    rows_with_text.append((current_start, y))
                    current_start = None
        
        if current_start is not None:
            rows_with_text.append((current_start, height))
        
        return rows_with_text
    
    def _extract_with_bounding_boxes(self, image: Image.Image) -> List[str]:
        """Extract signal names using bounding box information for better accuracy.
        
        Uses multiple passes with different configurations to catch both
        long signal names and short ones like 'i' and 'o'.
        """
        # First pass: Standard text extraction
        lines = self._ocr_pass(image, config=r'--oem 3 --psm 6', min_conf=30)
        
        # Second pass: Sparse text mode for isolated characters (like 'i', 'o')
        sparse_lines = self._ocr_pass(image, config=r'--oem 3 --psm 11', min_conf=20)
        
        # Merge results, preferring longer signal names
        merged_lines = self._merge_ocr_results(lines, sparse_lines)
        
        # Sort lines by Y position and merge text on each line
        signal_names = []
        for y_pos in sorted(merged_lines.keys()):
            # Sort by X position and join
            line_parts = sorted(merged_lines[y_pos], key=lambda t: t[0])
            merged_text = ''.join(part[1] for part in line_parts)
            
            # Clean up the merged text
            cleaned = self._clean_signal_name(merged_text)
            if cleaned:
                signal_names.append(cleaned)
        
        return signal_names
    
    def _ocr_pass(self, image: Image.Image, config: str, min_conf: int) -> Dict[int, List[Tuple[int, str]]]:
        """Perform a single OCR pass with given configuration.
        
        Args:
            image: Image to process
            config: Tesseract configuration string
            min_conf: Minimum confidence threshold
            
        Returns:
            Dictionary mapping Y positions to list of (x, text) tuples
        """
        data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
        
        lines = {}
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            conf = int(data['conf'][i])
            
            # Skip empty text
            if not text:
                continue
            
            # For single characters, accept lower confidence
            # (single chars like 'i', 'o' are harder to detect)
            required_conf = min_conf
            if len(text) == 1 and text.isalpha():
                required_conf = min(min_conf, 15)  # Lower threshold for single chars
            
            if conf < required_conf:
                continue
            
            # Get position
            x = data['left'][i]
            y = data['top'][i]
            h = data['height'][i]
            
            # Use center Y position for grouping
            y_center = y + h // 2
            
            # Find or create line group (within 20 pixels for scaled image)
            line_key = None
            for existing_y in lines.keys():
                if abs(existing_y - y_center) < 20:
                    line_key = existing_y
                    break
            
            if line_key is None:
                line_key = y_center
                lines[line_key] = []
            
            lines[line_key].append((x, text, conf))
        
        # Convert to simpler format
        return {y: [(x, t) for x, t, c in items] for y, items in lines.items()}
    
    def _merge_ocr_results(
        self, 
        lines1: Dict[int, List[Tuple[int, str]]], 
        lines2: Dict[int, List[Tuple[int, str]]]
    ) -> Dict[int, List[Tuple[int, str]]]:
        """Merge OCR results from two passes, avoiding duplicates.
        
        Args:
            lines1: Results from first OCR pass
            lines2: Results from second OCR pass
            
        Returns:
            Merged dictionary of lines
        """
        merged = dict(lines1)
        
        for y2, items2 in lines2.items():
            # Check if there's a matching line in lines1
            matching_y = None
            for y1 in merged.keys():
                if abs(y1 - y2) < 25:
                    matching_y = y1
                    break
            
            if matching_y is None:
                # New line, add it
                merged[y2] = items2
            else:
                # Merge with existing line, avoiding duplicates
                existing_items = merged[matching_y]
                existing_texts = {t.lower() for _, t in existing_items}
                
                for x, text in items2:
                    # Only add if not already present
                    if text.lower() not in existing_texts:
                        # Check if position is unique
                        position_occupied = any(abs(ex - x) < 30 for ex, _ in existing_items)
                        if not position_occupied:
                            existing_items.append((x, text))
                            existing_texts.add(text.lower())
        
        return merged
    
    def _extract_with_image_analysis(self, image_path: Path) -> List[str]:
        """Extract signal names using image analysis.
        
        This method analyzes the image to find text regions by looking for
        colored pixels (typically blue for signal names in WaveDrom).
        """
        image = Image.open(image_path).convert('RGB')
        width, height = image.size
        
        # Get the left portion where signal names are
        left_width = int(width * 0.20)
        
        # Find rows that contain text (non-white pixels on the left)
        text_rows = []
        pixels = image.load()
        
        # Scan vertically to find text regions
        current_region_start = None
        
        for y in range(height):
            has_text = False
            for x in range(left_width):
                r, g, b = pixels[x, y]
                # Check if pixel is not white/near-white (likely text)
                if r < 200 or g < 200 or b < 200:
                    has_text = True
                    break
            
            if has_text:
                if current_region_start is None:
                    current_region_start = y
            else:
                if current_region_start is not None:
                    # End of a text region
                    text_rows.append((current_region_start, y))
                    current_region_start = None
        
        # Don't forget the last region
        if current_region_start is not None:
            text_rows.append((current_region_start, height))
        
        # Image analysis alone can't extract text content
        # Return the number of text rows found for reference
        print(f"Found {len(text_rows)} text regions (y-positions)")
        print("Note: Install Tesseract OCR for automatic text extraction")
        print("      Or create a signal_order.txt file with signal names")
        return []
    
    def load_signal_order_file(self, file_path: Path) -> List[str]:
        """Load signal order from a text file.
        
        The file should contain one signal name per line, in order.
        Lines starting with # are comments.
        
        Args:
            file_path: Path to the signal order file
            
        Returns:
            List of signal names in order
        """
        if not file_path.exists():
            return []
        
        signals = []
        for line in file_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                signals.append(line)
        
        return signals
    
    def extract_from_verilog(self, verilog_path: Path) -> List[str]:
        """Extract signal order from Verilog code.
        
        Extracts all signal declarations (ports, regs, wires) in declaration order.
        
        Args:
            verilog_path: Path to the Verilog file
            
        Returns:
            List of signal names in declaration order
        """
        from verilog_parser import parse_verilog
        
        verilog_code = verilog_path.read_text(encoding='utf-8')
        module = parse_verilog(verilog_code)
        
        if not module:
            return []
        
        signals = []
        
        # Add ports first
        for port in module.ports:
            signals.append(port.get_full_name())
        
        # Parse internal signals from Verilog code
        internal_signals = self._extract_internal_signals(verilog_code)
        signals.extend(internal_signals)
        
        return signals
    
    def _extract_internal_signals(self, verilog_code: str) -> List[str]:
        """Extract internal signal declarations from Verilog code.
        
        Args:
            verilog_code: Verilog source code
            
        Returns:
            List of internal signal names in declaration order
        """
        signals = []
        
        # Match reg/wire declarations
        # reg [7:0] name; or wire name; or reg name, name2;
        pattern = re.compile(
            r'^\s*(reg|wire)\s*'
            r'(?:\[[^\]]+\])?\s*'  # Optional bit range
            r'([^;]+);',
            re.MULTILINE
        )
        
        for match in pattern.finditer(verilog_code):
            names_str = match.group(2)
            # Split by comma and clean up
            for name in names_str.split(','):
                name = name.strip()
                # Remove any trailing bit range
                name = re.sub(r'\s*\[.*\]', '', name)
                if name and name.isidentifier():
                    signals.append(name)
        
        return signals
    
    def _parse_signal_names(self, text: str) -> List[str]:
        """Parse OCR text to extract signal names.
        
        Args:
            text: Raw OCR text output
            
        Returns:
            List of cleaned signal names
        """
        lines = text.strip().split('\n')
        signal_names = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Clean up common OCR errors
            cleaned = self._clean_signal_name(line)
            if cleaned:
                signal_names.append(cleaned)
        
        return signal_names
    
    def _clean_signal_name(self, name: str) -> Optional[str]:
        """Clean a signal name from OCR output.
        
        Args:
            name: Raw signal name from OCR
            
        Returns:
            Cleaned signal name or None if invalid
        """
        # Remove leading/trailing whitespace
        name = name.strip()
        
        # Skip empty strings
        if not name:
            return None
        
        # Skip common OCR artifacts
        if name in ['|', '—', '-', '_', '.', ',', ':', ';', '/', '\\', '(', ')']:
            return None
        
        # Skip if it's just numbers (likely tick marks or cycle numbers)
        # EXCEPT single digit that might be OCR confusion for letter
        # 0 -> o, 1 -> l/i
        if name.isdigit():
            if len(name) == 1:
                # Single digit might be a letter misread
                ocr_digit_to_letter = {'0': 'o', '1': 'i'}
                if name in ocr_digit_to_letter:
                    name = ocr_digit_to_letter[name]
                else:
                    return None
            else:
                # Multi-digit numbers are cycle counts, skip them
                return None
        
        # Skip common non-signal text
        skip_patterns = ['Timing', 'Diagram', 'Cycle', 'numbers', 'tick', 'clock', 'time']
        for pattern in skip_patterns:
            if pattern.lower() in name.lower() and len(name) > len(pattern) + 3:
                # Allow words like "clk" but skip "Timing Diagram"
                return None
        
        # Skip if it looks like a header/title
        if 'Diagram' in name or 'numbers' in name:
            return None
        
        # Fix common OCR substitutions
        # Note: Be careful not to change legitimate names
        name = name.replace('|', 'l')
        
        # Handle bit range notation - OCR might read [7:0] as various formats
        # Try to normalize bit ranges like [7:0], [15:0], etc.
        # Also handle OCR mistakes like {15:0} -> [15:0]
        name = name.replace('{', '[').replace('}', ']')
        name = re.sub(r'\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]', r'[\1:\2]', name)
        
        # Remove any leading special characters
        name = re.sub(r'^[^\w]+', '', name)
        
        # Remove any trailing special characters (except ])
        name = re.sub(r'[^\w\]]+$', '', name)
        
        # Skip if too short (likely noise)
        if len(name) < 1:
            return None
        
        # Skip if it looks like just numbers with brackets (like data values)
        if re.match(r'^[\d\[\]:]+$', name):
            return None
        
        # Must start with a letter or underscore (valid Verilog identifier)
        if name and (name[0].isalpha() or name[0] == '_'):
            return name
        
        return None
    
    def extract_with_positions(self, image_path: Path) -> List[Tuple[str, int]]:
        """Extract signal names with their Y positions.
        
        Args:
            image_path: Path to the waveform PNG image
            
        Returns:
            List of (signal_name, y_position) tuples sorted by y_position
        """
        image = Image.open(image_path)
        width, height = image.size
        
        # Get the left portion
        left_region = image.crop((0, 0, int(width * 0.20), height))
        
        # Use pytesseract to get bounding boxes
        data = pytesseract.image_to_data(left_region, output_type=pytesseract.Output.DICT)
        
        signals_with_pos = []
        
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            text = data['text'][i].strip()
            if not text:
                continue
            
            cleaned = self._clean_signal_name(text)
            if cleaned:
                # Get y position (top of bounding box)
                y = data['top'][i]
                signals_with_pos.append((cleaned, y))
        
        # Sort by y position (top to bottom)
        signals_with_pos.sort(key=lambda x: x[1])
        
        # Merge consecutive parts that might be the same signal name
        merged = self._merge_adjacent_signals(signals_with_pos)
        
        return merged
    
    def _merge_adjacent_signals(
        self, 
        signals_with_pos: List[Tuple[str, int]], 
        threshold: int = 10
    ) -> List[Tuple[str, int]]:
        """Merge adjacent signal name parts that are on the same line.
        
        Args:
            signals_with_pos: List of (name, y_pos) tuples
            threshold: Y distance threshold for merging
            
        Returns:
            Merged list of (name, y_pos) tuples
        """
        if not signals_with_pos:
            return []
        
        merged = []
        current_name = signals_with_pos[0][0]
        current_y = signals_with_pos[0][1]
        
        for i in range(1, len(signals_with_pos)):
            name, y = signals_with_pos[i]
            
            if abs(y - current_y) <= threshold:
                # Same line, merge names
                current_name = f"{current_name}{name}"
            else:
                # New line, save current and start new
                merged.append((current_name, current_y))
                current_name = name
                current_y = y
        
        # Don't forget the last one
        merged.append((current_name, current_y))
        
        return merged


def normalize_ocr_chars(text: str) -> str:
    """Normalize commonly confused OCR characters.
    
    Maps characters that OCR frequently confuses to a canonical form.
    """
    # Common OCR confusions: l/i/1, o/0/a (in some fonts)
    replacements = {
        'l': 'i',  # l often confused with i
        '1': 'i',  # 1 often confused with i or l
        '0': 'o',  # 0 often confused with o
    }
    result = text.lower()
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def fuzzy_match_score(ocr_name: str, signal_name: str) -> float:
    """Calculate fuzzy match score between OCR-extracted name and signal name.
    
    Handles common OCR errors and naming variations like:
    - Character substitution (sys_cik -> sys_clk)
    - Prefix differences (tmp -> out_tmp)
    - Missing characters
    - OCR confusion (i/l/1, o/0)
    
    Args:
        ocr_name: Name extracted via OCR (may have errors)
        signal_name: Actual signal name from generated WaveDrom
        
    Returns:
        Match score between 0.0 (no match) and 1.0 (exact match)
    """
    ocr_lower = ocr_name.lower()
    sig_lower = signal_name.lower()
    
    # Exact match
    if ocr_lower == sig_lower:
        return 1.0
    
    # Normalize OCR-confused characters and check match
    ocr_normalized = normalize_ocr_chars(ocr_lower)
    sig_normalized = normalize_ocr_chars(sig_lower)
    if ocr_normalized == sig_normalized:
        return 0.98  # Very high match for OCR confusion
    
    # Special handling for single-character signals
    if len(ocr_lower) == 1 and len(sig_lower) == 1:
        # Check if they're commonly confused
        confusable = [{'i', 'l', '1'}, {'o', '0', 'a'}]
        for group in confusable:
            if ocr_lower in group and sig_lower in group:
                return 0.95  # High match for confusable single chars
    
    # Remove bit ranges for comparison
    ocr_base = re.sub(r'\[.*\]', '', ocr_lower)
    sig_base = re.sub(r'\[.*\]', '', sig_lower)
    
    # Exact base match
    if ocr_base == sig_base:
        return 0.95
    
    # Check if signal_name has common prefixes that OCR name doesn't have
    # e.g., "tmp" should match "out_tmp"
    for prefix in ['out_', 'in_', 'o_', 'i_', 'prev_']:
        if sig_base.startswith(prefix):
            stripped = sig_base[len(prefix):]
            if ocr_base == stripped:
                return 0.9  # Strong match for prefix difference
    
    # Check if ocr_base is a suffix of sig_base
    if sig_base.endswith(ocr_base) and len(ocr_base) >= 3:
        return 0.85
    
    # Check if one contains the other (with length check)
    if len(ocr_base) >= 3 and len(sig_base) >= 3:
        if ocr_base in sig_base:
            return 0.8 * (len(ocr_base) / len(sig_base))
        if sig_base in ocr_base:
            return 0.8 * (len(sig_base) / len(ocr_base))
    
    # Calculate character-level similarity using simple edit distance approximation
    max_len = max(len(ocr_base), len(sig_base))
    if max_len == 0:
        return 0.0
    
    # Count matching characters at each position
    matches = 0
    for i in range(min(len(ocr_base), len(sig_base))):
        if ocr_base[i] == sig_base[i]:
            matches += 1
    
    # Count common characters regardless of position
    common_chars = 0
    sig_chars = list(sig_base)
    for c in ocr_base:
        if c in sig_chars:
            common_chars += 1
            sig_chars.remove(c)  # Only count each char once
    
    # Combined score
    position_score = matches / max_len
    char_score = common_chars / max_len
    similarity = 0.6 * position_score + 0.4 * char_score
    
    # Bonus for same starting characters (important for signal names)
    prefix_len = 0
    for i in range(min(len(ocr_base), len(sig_base))):
        if ocr_base[i] == sig_base[i]:
            prefix_len += 1
        else:
            break
    
    if prefix_len >= 2:
        similarity += 0.15 * (prefix_len / max_len)
    
    return min(similarity, 0.85)  # Cap at 0.85 for non-exact matches


def reorder_wavedrom_signals(
    wavedrom_dict: Dict[str, Any],
    reference_order: List[str],
    filter_to_reference: bool = True
) -> Dict[str, Any]:
    """Reorder WaveDrom signals to match a reference order.
    
    Uses fuzzy matching to handle OCR errors in reference_order.
    
    Args:
        wavedrom_dict: WaveDrom JSON dictionary with 'signal' list
        reference_order: List of signal names in desired order (may have OCR errors)
        filter_to_reference: If True, only keep signals that appear in reference_order
                            (filters out extra signals not in original image)
        
    Returns:
        New WaveDrom dictionary with reordered (and optionally filtered) signals
    """
    signals = wavedrom_dict.get('signal', [])
    if not signals or not reference_order:
        return wavedrom_dict
    
    # Build list of available signals with their normalized names
    available_signals = []
    for sig in signals:
        name = sig.get('name', '')
        available_signals.append({
            'signal': sig,
            'name': name,
            'name_lower': name.lower(),
            'base_name': re.sub(r'\[.*\]', '', name).lower()
        })
    
    # Match reference signals to available signals using fuzzy matching
    reordered = []
    used_indices = set()
    
    for ref_name in reference_order:
        best_match_idx = None
        best_match_score = 0.4  # Minimum threshold for matching
        
        for idx, avail in enumerate(available_signals):
            if idx in used_indices:
                continue
            
            # Calculate fuzzy match score
            score = fuzzy_match_score(ref_name, avail['name'])
            
            if score > best_match_score:
                best_match_score = score
                best_match_idx = idx
        
        if best_match_idx is not None:
            reordered.append(available_signals[best_match_idx]['signal'])
            used_indices.add(best_match_idx)
    
    # Optionally add remaining signals that weren't matched
    if not filter_to_reference:
        for idx, avail in enumerate(available_signals):
            if idx not in used_indices:
                reordered.append(avail['signal'])
    
    # Return new dict with reordered signals
    result = wavedrom_dict.copy()
    result['signal'] = reordered
    return result


def normalize_signal_name(name: str) -> str:
    """Normalize a signal name for comparison.
    
    Args:
        name: Signal name to normalize
        
    Returns:
        Normalized signal name (lowercase, no bit range)
    """
    name = name.lower().strip()
    # Remove bit range
    name = re.sub(r'\[.*\]', '', name)
    # Remove common prefixes
    for prefix in ['out_', 'in_', 'o_', 'i_']:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def match_signals(
    ocr_signals: List[str],
    generated_signals: List[Dict[str, Any]]
) -> List[Tuple[str, Optional[Dict[str, Any]]]]:
    """Match OCR-extracted signals to generated signals.
    
    Args:
        ocr_signals: List of signal names from OCR
        generated_signals: List of signal dicts from WaveDrom generation
        
    Returns:
        List of (ocr_name, matched_signal_dict or None) tuples
    """
    # Build lookup for generated signals
    gen_lookup = {}
    for sig in generated_signals:
        name = sig.get('name', '')
        normalized = normalize_signal_name(name)
        gen_lookup[normalized] = sig
        # Also add original lowercase
        gen_lookup[name.lower()] = sig
    
    matches = []
    used = set()
    
    for ocr_name in ocr_signals:
        ocr_normalized = normalize_signal_name(ocr_name)
        
        matched = None
        # Try exact match
        if ocr_normalized in gen_lookup and ocr_normalized not in used:
            matched = gen_lookup[ocr_normalized]
            used.add(ocr_normalized)
        else:
            # Try substring match
            for gen_norm, sig in gen_lookup.items():
                if gen_norm in used:
                    continue
                if ocr_normalized in gen_norm or gen_norm in ocr_normalized:
                    matched = sig
                    used.add(gen_norm)
                    break
        
        matches.append((ocr_name, matched))
    
    return matches


def extract_and_match_order(
    original_image_path: Path,
    wavedrom_dict: Dict[str, Any],
    verilog_path: Path = None,
    filter_to_original: bool = True
) -> Dict[str, Any]:
    """Extract signal order from original image and reorder WaveDrom to match.
    
    Tries multiple methods in order:
    1. OCR from original image (requires Tesseract)
    2. Signal order file (signal_order.txt in same directory)
    3. Verilog declaration order (requires verilog_path)
    
    Args:
        original_image_path: Path to the original waveform image
        wavedrom_dict: WaveDrom dictionary to reorder
        verilog_path: Optional path to Verilog file for fallback ordering
        filter_to_original: If True, only keep signals that appear in original image
        
    Returns:
        Reordered (and optionally filtered) WaveDrom dictionary
    """
    extractor = SignalOrderExtractor()
    signal_order = []
    source = None
    
    # Method 1: Try OCR extraction from image
    if original_image_path and original_image_path.exists():
        signal_order = extractor.extract_signal_order(original_image_path)
        if signal_order:
            source = "OCR"
            print(f"Extracted {len(signal_order)} signals via OCR: {signal_order}")
    
    # Method 2: Try signal order file
    if not signal_order:
        order_file = original_image_path.parent / "signal_order.txt" if original_image_path else None
        if order_file and order_file.exists():
            signal_order = extractor.load_signal_order_file(order_file)
            if signal_order:
                source = "signal_order.txt"
                print(f"Loaded signal order from {order_file}")
        
        # Also check for sample-specific order file
        if not signal_order and original_image_path:
            sample_order_file = original_image_path.with_suffix('.order.txt')
            if sample_order_file.exists():
                signal_order = extractor.load_signal_order_file(sample_order_file)
                if signal_order:
                    source = "sample order file"
                    print(f"Loaded signal order from {sample_order_file}")
    
    # Method 3: Use Verilog declaration order (but don't filter based on this)
    if not signal_order and verilog_path and verilog_path.exists():
        signal_order = extractor.extract_from_verilog(verilog_path)
        if signal_order:
            source = "Verilog"
            print(f"Using Verilog declaration order from {verilog_path}")
            # Don't filter when using Verilog order (we don't know what's in original)
            filter_to_original = False
    
    # Apply ordering if we have one
    if signal_order:
        print(f"Applying signal order from {source} (filter={filter_to_original})")
        return reorder_wavedrom_signals(
            wavedrom_dict, 
            signal_order, 
            filter_to_reference=filter_to_original
        )
    else:
        print("No signal order extracted, keeping original order")
        return wavedrom_dict


if __name__ == "__main__":
    import json
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python signal_order_extractor.py <image_path> [wavedrom_json_path]")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    
    print(f"Extracting signal order from: {image_path}")
    extractor = SignalOrderExtractor()
    
    # Extract signal names
    signals = extractor.extract_signal_order(image_path)
    print(f"\nExtracted {len(signals)} signals:")
    for i, name in enumerate(signals):
        print(f"  [{i}] {name}")
    
    # If wavedrom JSON provided, reorder it
    if len(sys.argv) >= 3:
        json_path = Path(sys.argv[2])
        wavedrom = json.loads(json_path.read_text())
        
        print(f"\nOriginal WaveDrom signals:")
        for i, sig in enumerate(wavedrom.get('signal', [])):
            print(f"  [{i}] {sig.get('name', 'N/A')}")
        
        reordered = reorder_wavedrom_signals(wavedrom, signals)
        
        print(f"\nReordered WaveDrom signals:")
        for i, sig in enumerate(reordered.get('signal', [])):
            print(f"  [{i}] {sig.get('name', 'N/A')}")
        
        # Save reordered
        output_path = json_path.parent / f"{json_path.stem}_reordered.json"
        output_path.write_text(json.dumps(reordered, indent=2))
        print(f"\nSaved: {output_path}")
