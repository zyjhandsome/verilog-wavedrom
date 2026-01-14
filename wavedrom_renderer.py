"""
WaveDrom Renderer - Render WaveDrom JSON to PNG images.

Supports multiple rendering backends:
1. Python wavedrom + Playwright (headless browser)
2. Python wavedrom + cairosvg
3. wavedrom-cli (Node.js)
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional


def check_dependencies() -> Dict[str, bool]:
    """Check which rendering methods are available."""
    deps = {}
    
    # Check for wavedrom-cli (npx wavedrom-cli)
    deps['wavedrom-cli'] = shutil.which('npx') is not None
    
    # Check for Python wavedrom library
    try:
        import wavedrom
        deps['wavedrom-py'] = True
    except ImportError:
        deps['wavedrom-py'] = False
    
    # Check for Playwright (headless browser rendering)
    try:
        from playwright.sync_api import sync_playwright
        deps['playwright'] = True
    except ImportError:
        deps['playwright'] = False
    
    # Check for cairosvg (for SVG to PNG conversion)
    try:
        import cairosvg
        deps['cairosvg'] = True
    except (ImportError, OSError):
        deps['cairosvg'] = False
    
    return deps


class WaveDromRenderer:
    """Render WaveDrom JSON to PNG images."""
    
    def __init__(self):
        self.deps = check_dependencies()
    
    def render_to_png(self, wavedrom_dict: Dict[str, Any]) -> bytes:
        """Render WaveDrom JSON to PNG bytes."""
        # Try Python wavedrom + Playwright first (most reliable on Windows)
        if self.deps.get('wavedrom-py') and self.deps.get('playwright'):
            try:
                return self._render_with_playwright(wavedrom_dict)
            except Exception as e:
                # Fall through to other methods if Playwright fails
                pass
        
        # Try Python wavedrom + cairosvg
        if self.deps.get('wavedrom-py') and self.deps.get('cairosvg'):
            try:
                return self._render_with_cairosvg(wavedrom_dict)
            except Exception:
                pass
        
        # Fall back to wavedrom-cli
        if self.deps.get('wavedrom-cli'):
            return self._render_with_cli(wavedrom_dict)
        
        raise RuntimeError(
            "No rendering method available. Install one of:\n"
            "  - pip install wavedrom playwright && playwright install chromium\n"
            "  - pip install wavedrom cairosvg (requires Cairo library)\n"
            "  - npm install -g wavedrom-cli"
        )
    
    def _render_with_playwright(self, wavedrom_dict: Dict[str, Any]) -> bytes:
        """Render using Python wavedrom + Playwright headless browser."""
        import wavedrom
        from playwright.sync_api import sync_playwright
        
        # Generate SVG using wavedrom library (needs JSON string, not dict)
        svg = wavedrom.render(json.dumps(wavedrom_dict))
        svg_str = svg.tostring()
        
        # Create HTML page with SVG
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ margin: 0; padding: 10px; background: white; }}
        svg {{ display: block; }}
    </style>
</head>
<body>
{svg_str}
</body>
</html>"""
        
        # Use Playwright to render to PNG
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            html_file = tmpdir / "waveform.html"
            html_file.write_text(html_content, encoding='utf-8')
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file:///{html_file.as_posix()}")
                
                # Wait for SVG to render
                page.wait_for_selector("svg")
                
                # Get SVG bounding box and screenshot
                svg_element = page.query_selector("svg")
                png_bytes = svg_element.screenshot()
                
                browser.close()
                
            return png_bytes
    
    def _render_with_cairosvg(self, wavedrom_dict: Dict[str, Any]) -> bytes:
        """Render using Python wavedrom + cairosvg."""
        import wavedrom
        import cairosvg
        
        # Generate SVG (needs JSON string, not dict)
        svg = wavedrom.render(json.dumps(wavedrom_dict))
        svg_str = svg.tostring()
        
        # Convert SVG to PNG
        png_bytes = cairosvg.svg2png(bytestring=svg_str)
        return png_bytes
    
    def _render_with_cli(self, wavedrom_dict: Dict[str, Any]) -> bytes:
        """Render using wavedrom-cli."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Write JSON file
            json_file = tmpdir / "waveform.json"
            json_file.write_text(json.dumps(wavedrom_dict), encoding='utf-8')
            
            # Output PNG file
            png_file = tmpdir / "waveform.png"
            
            # Run wavedrom-cli
            try:
                result = subprocess.run(
                    ['npx', 'wavedrom-cli', '-i', str(json_file), '-p', str(png_file)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    raise RuntimeError(f"wavedrom-cli failed: {result.stderr}")
                
                # Read PNG file
                return png_file.read_bytes()
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("wavedrom-cli timed out")
            except FileNotFoundError:
                raise RuntimeError("npx not found - install Node.js")
    
    def render_to_file(self, wavedrom_dict: Dict[str, Any], output_path: Path) -> None:
        """Render WaveDrom JSON to a PNG file."""
        png_bytes = self.render_to_png(wavedrom_dict)
        Path(output_path).write_bytes(png_bytes)


if __name__ == "__main__":
    print("Checking dependencies...")
    deps = check_dependencies()
    for name, available in deps.items():
        status = "OK" if available else "MISSING"
        print(f"  {name}: {status}")
    
    # Test rendering if wavedrom is available
    if deps.get('wavedrom-py') and (deps.get('playwright') or deps.get('cairosvg')):
        print("\nTesting rendering...")
        test_wavedrom = {
            "signal": [
                {"name": "clk", "wave": "p...."},
                {"name": "data", "wave": "x.=.=", "data": ["A", "B"]}
            ]
        }
        renderer = WaveDromRenderer()
        try:
            png_bytes = renderer.render_to_png(test_wavedrom)
            print(f"  Rendering successful! PNG size: {len(png_bytes)} bytes")
        except Exception as e:
            print(f"  Rendering failed: {e}")
