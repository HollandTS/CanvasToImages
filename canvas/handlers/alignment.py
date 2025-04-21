import logging

class AlignmentHandler:
    def __init__(self, canvas_window):
        self.canvas_window = canvas_window
        self.move_step = 2  # Default step size for movement

    def set_move_step(self, step):
        """Set the movement step size."""
        try:
            step_value = int(step)
            if step_value > 0:
                self.move_step = step_value
                return True
        except (ValueError, TypeError):
            pass
        return False

    def get_move_step(self):
        """Get the current movement step size."""
        return self.move_step

    def _get_grid_points(self):
        """Get grid points based on current grid type."""
        try:
            grid_info = self.canvas_window.current_grid_info
            if not grid_info:
                return None

            grid_type = grid_info.get('type')
            canvas_width = self.canvas_window.canvas_world_width
            canvas_height = self.canvas_window.canvas_world_height
            
            if grid_type == "pixel":
                step = grid_info.get('step')
                if not step or step <= 0:
                    return None
                
                x_points = list(range(0, canvas_width + step, step))
                y_points = list(range(0, canvas_height + step, step))
                
            elif grid_type == "diamond":
                cell_w = grid_info.get('cell_width')
                cell_h = grid_info.get('cell_height')
                if not cell_w or cell_w <= 0 or not cell_h or cell_h <= 0:
                    return None
                    
                x_points = list(range(0, canvas_width + cell_w, cell_w))
                y_points = list(range(0, canvas_height + cell_h, cell_h))
                
            else:
                return None

            return {'x_points': x_points, 'y_points': y_points}
            
        except Exception as e:
            logging.error(f"Error getting grid points: {e}", exc_info=True)
            return None

    def _get_selected_items(self):
        """Get currently selected items."""
        try:
            selected_items = []
            item_ids = (self.canvas_window.selected_item_ids.copy() if self.canvas_window.selected_item_ids 
                       else {self.canvas_window.last_clicked_item_id} if self.canvas_window.last_clicked_item_id 
                       else set())

            for item_id in item_ids:
                for filename, data in self.canvas_window.images.items():
                    if data['id'] == item_id:
                        selected_items.append({
                            'id': item_id,
                            'x': data['x'],
                            'y': data['y'],
                            'width': data['image'].width,
                            'height': data['image'].height,
                            'data': data
                        })
                        break

            return selected_items
        except Exception as e:
            logging.error(f"Error getting selected items: {e}", exc_info=True)
            return []

    def _find_nearest_point(self, value, points):
        """Find the nearest grid point to a given value."""
        if not points:
            return value
        return min(points, key=lambda x: abs(x - value))

    def _update_item_position(self, item, x, y):
        """Update an item's position on the canvas."""
        try:
            item['data']['x'] = x
            item['data']['y'] = y
            self.canvas_window.canvas.coords(item['id'], x, y)
        except Exception as e:
            logging.error(f"Error updating item position: {e}", exc_info=True)

    def align_left(self):
        """Move selected items left by step size."""
        try:
            items = self._get_selected_items()
            if not items:
                logging.info("No items selected for movement")
                return False

            for item in items:
                new_x = item['x'] - self.move_step
                self._update_item_position(item, new_x, item['y'])

            self.canvas_window.canvas.update_idletasks()
            return True

        except Exception as e:
            logging.error(f"Error in left movement: {e}", exc_info=True)
            return False

    def align_right(self):
        """Move selected items right by step size."""
        try:
            items = self._get_selected_items()
            if not items:
                logging.info("No items selected for movement")
                return False

            for item in items:
                new_x = item['x'] + self.move_step
                self._update_item_position(item, new_x, item['y'])

            self.canvas_window.canvas.update_idletasks()
            return True

        except Exception as e:
            logging.error(f"Error in right movement: {e}", exc_info=True)
            return False

    def align_top(self):
        """Move selected items up by step size."""
        try:
            items = self._get_selected_items()
            if not items:
                logging.info("No items selected for movement")
                return False

            for item in items:
                new_y = item['y'] - self.move_step
                self._update_item_position(item, item['x'], new_y)

            self.canvas_window.canvas.update_idletasks()
            return True

        except Exception as e:
            logging.error(f"Error in top movement: {e}", exc_info=True)
            return False

    def align_bottom(self):
        """Move selected items down by step size."""
        try:
            items = self._get_selected_items()
            if not items:
                logging.info("No items selected for movement")
                return False

            for item in items:
                new_y = item['y'] + self.move_step
                self._update_item_position(item, item['x'], new_y)

            self.canvas_window.canvas.update_idletasks()
            return True

        except Exception as e:
            logging.error(f"Error in bottom movement: {e}", exc_info=True)
            return False 