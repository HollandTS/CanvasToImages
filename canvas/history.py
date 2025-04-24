import logging
from dataclasses import dataclass
from typing import Dict, Any, List
import copy

@dataclass
class HistoryState:
    images: Dict[str, Any]
    selected_item_ids: set
    last_clicked_item_id: Any
    overlay_image: Any
    layer_behind: bool

class HistoryManager:
    def __init__(self, max_history=50):
        self.max_history = max_history
        self.history: List[HistoryState] = []
        self.current_index = -1
        
    def push_state(self, canvas_window):
        """Add current canvas state to history."""
        try:
            # Create a deep copy of the current state
            state = HistoryState(
                images=copy.deepcopy(canvas_window.images),
                selected_item_ids=set(canvas_window.selected_item_ids),
                last_clicked_item_id=canvas_window.last_clicked_item_id,
                overlay_image=canvas_window.pasted_overlay_pil_image.copy() if canvas_window.pasted_overlay_pil_image else None,
                layer_behind=canvas_window.layer_behind
            )
            
            # Remove any states after current index (in case of new action after undo)
            self.history = self.history[:self.current_index + 1]
            
            # Add new state
            self.history.append(state)
            self.current_index += 1
            
            # Remove oldest states if exceeding max_history
            if len(self.history) > self.max_history:
                self.history.pop(0)
                self.current_index -= 1
                
        except Exception as e:
            logging.error(f"Error pushing state to history: {e}", exc_info=True)
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return self.current_index > 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return self.current_index < len(self.history) - 1
    
    def undo(self, canvas_window):
        """Restore previous state."""
        if not self.can_undo():
            return
            
        try:
            self.current_index -= 1
            self._restore_state(canvas_window, self.history[self.current_index])
        except Exception as e:
            logging.error(f"Error performing undo: {e}", exc_info=True)
    
    def redo(self, canvas_window):
        """Restore next state."""
        if not self.can_redo():
            return
            
        try:
            self.current_index += 1
            self._restore_state(canvas_window, self.history[self.current_index])
        except Exception as e:
            logging.error(f"Error performing redo: {e}", exc_info=True)
    
    def _restore_state(self, canvas_window, state: HistoryState):
        """Restore canvas to given state."""
        try:
            # Clear current canvas state
            canvas_window.canvas.delete("all")
            canvas_window.images.clear()
            canvas_window.selected_item_ids.clear()
            
            # Restore images and their states
            canvas_window.images = copy.deepcopy(state.images)
            canvas_window.selected_item_ids = set(state.selected_item_ids)
            canvas_window.last_clicked_item_id = state.last_clicked_item_id
            
            # Restore overlay if exists
            canvas_window.pasted_overlay_pil_image = state.overlay_image.copy() if state.overlay_image else None
            canvas_window.layer_behind = state.layer_behind
            
            # Redraw canvas with restored state
            canvas_window.redraw_canvas()
            
        except Exception as e:
            logging.error(f"Error restoring state: {e}", exc_info=True) 