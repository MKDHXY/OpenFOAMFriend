"""Small monochrome drafting symbols; no raster mockups or button frames."""
from PySide6.QtGui import QIcon,QPixmap,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray,Qt

PATHS={
 'Select':'<path d="M5 3v16l4-5 4 7 3-2-4-6 6-1z"/>',
 'Pan':'<path d="M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/>',
 'Line':'<path d="M4 19L20 5"/><circle cx="4" cy="19" r="2"/><circle cx="20" cy="5" r="2"/>',
 'Polyline':'<path d="M3 18l6-12 7 10 5-11"/>',
 'Circle':'<circle cx="12" cy="12" r="8"/><path d="M9 12h6M12 9v6"/>',
 'Rectangle':'<rect x="3" y="5" width="18" height="14"/>',
 'Triangle':'<path d="M12 3L3 21h18z"/>',
 'Mesh region':'<rect x="3" y="3" width="18" height="18" stroke-dasharray="2 2"/><path d="M9 4v16M15 4v16M4 9h16M4 15h16"/>',
 'Eraser':'<path d="M4 15l9-11 8 7-8 10H9zM8 10l8 7M13 21h8"/>',
 'Measure':'<path d="M3 6h18v12H3zM7 6v6M11 6v4M15 6v6M19 6v4"/>',
 'Precise shape':'<circle cx="12" cy="12" r="6"/><path d="M12 2v6M12 16v6M2 12h6M16 12h6"/>',
 'Exact line':'<path d="M4 18L20 6M4 14v7M20 3v7"/>',
 'Mesh spacing':'<path d="M3 3v18M6 3v18M11 3v18M19 3v18M2 12h20"/>',
 'Initial fields / dictionaries':'<path d="M7 3H4v18h3M17 3h3v18h-3M9 7h6M9 12h6M9 17h6"/>',
 'Sketch settings':'<path d="M3 6h18M3 12h18M3 18h18M8 3v6M16 9v6M10 15v6"/>',
 'Automatic mesh assistant':'<rect x="3" y="3" width="18" height="18"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
 'Design parameters / mesh code':'<path d="M8 5L2 12l6 7M16 5l6 7-6 7M14 3l-4 18"/>',
 'Undo':'<path d="M8 4L3 9l5 5M3 9h12a5 5 0 010 10h-4"/>',
 'Redo':'<path d="M16 4l5 5-5 5M21 9H9a5 5 0 000 10h4"/>',
 'Fit':'<path d="M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6"/>'}

def tool_icon(name):
    if name not in PATHS: return QIcon()
    data=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g stroke="#314c62" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
    pixmap=QPixmap(20,20); pixmap.fill(Qt.transparent); painter=QPainter(pixmap); QSvgRenderer(QByteArray(data.encode())).render(painter); painter.end(); return QIcon(pixmap)
