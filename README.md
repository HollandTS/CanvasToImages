# CanvasToImages
Tool to drag images onto a canvas, copy canvas, make edits with external tools, paste image back and save back to individual images.
First Alpha! Make backup of your images first. Use with care!

## Download EXE here:
[https://github.com/HollandTS/CanvasToImages/releases](https://github.com/HollandTS/CanvasToImages/releases)](https://github.com/HollandTS/CanvasToImages/releases)

(CanvaToImages.zip)

### How it works: 
Drag images onto the canvas, select transparency color (optional), copy the canvas (or save) to your clipboard by pressing the Copy Button. 
Make edits with external tools (like with AI, photoshop, etc)
use [Paste] to Paste the image back onto the canvas as overlay, move in place (if view remained unmoved it might not be nessecary).
Warning: Upon pressing 'Apply Canvas to Images': ALL IMAGES WILL BE SAVED IMMEDIATLY SO MAKE BACKUP OF IMAGES FIRST!
Press 'Apply Canvas to Images' to save all the individual images with the pasted overlay.

![cliff_preview](https://github.com/user-attachments/assets/759b57b4-795d-4287-b470-825eec7fdd28)
(the bug is fixed where some images dont get their transparency pasted back, get latest.)

### Top Controls:

- Transparency:
Use 'Pick color' to pick a color from the images in the canvas to select the transparency color.
Use 'Tolerance' if this color has a bigger range
Enable 'Invert' to invert transparency.

- Background:
Currently you can only just pick a color to be canvas background, might implement image bground later

- Capture/Paste:
[Save] to save the canvas as png, [Copy] to copy canvas image on clipboard.
Choose what to copy/save: View (the current view of canvas), Images only (topleft px to bottomright px), or Full canvas

- Layer:
[Del] to remove selected image(s). Hotkey: X or Delete

- Align:
Arrows to move selected image(s) by pixel steps. Hotkeys: Arrows

- Overlay:
Set the pasted overlay's Opacity, put overlay to Front or Back of layers/images

### Canvas Controls:

- left click to select, drag to move.
- Use your keyboard arrows to make minor adjustments (see Align)
- Right click-drag to box-select multiple images in canvas
- Hold middle mouse button (scrollwheel) to pan around
- Scroll mousewheel to zoom. Hotkey Z to Refresh to 100% zoom level
- 'Overlap' checkbox in bottomright is a bit buggy, avoid disabling for now.
- 'Snap' checkbox, will automatically snap on the grid.
- Ctrl Z - Undo
- Ctrl Y - Redo
Note: With snap enabled, you can loose the manual alignments (Arrow buttons). Make the alignment edits last.

### Bottom Controls:

- Grid (Optional): currently i only have a 2D test grid 2 pxls, and TS and RA2 (c&c games) presets! Clone a gridfile and use same name structure to create own grid. e.g.: 'iso 48w 24h' is for the game Tiberian Sun, '2d 4px' is just for flat 2d, 4 pixels wide.
- Canvas: Controls to set the size of the canvas if needed
- Palette: Load an image to set the colors closest to the image you loaded.
- Layout: Save and load all image placements on the canvas
- Show/hide Layers: shows/hides the layer panel: Here you see the image title's, drag them to change layer order. Arrow Buttons currently don't work

- Apply Canvas to Images: The magical button! Make sure to backup your images before using this button!

### File manager:
Simply press Load images to load images
use Ctrl and shift to select multiple images. Drag images onto canvas.

