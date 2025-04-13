import os
import tkinter as tk
from tkinter import ttk, filedialog

class FileManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Manager")

        self.tree = ttk.Treeview(self.root, columns=('Name', 'Size'), show='headings')
        self.tree.heading('Name', text='Name', command=lambda: self.sort_by_name())
        self.tree.heading('Size', text='Size', command=lambda: self.sort_by_size())
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.load_button = tk.Button(self.root, text="Load Directory", command=self.load_directory)
        self.load_button.pack()

        self.current_directory = None
        self.files = []

    def load_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.current_directory = directory
            self.populate_tree(directory)

    def populate_tree(self, directory):
        self.tree.delete(*self.tree.get_children())
        self.files = []

        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            size = os.path.getsize(filepath)
            self.files.append((filename, size))

        self.display_files()

    def display_files(self):
        for filename, size in self.files:
            self.tree.insert('', tk.END, values=(filename, size))

    def sort_by_name(self):
        self.files.sort(key=lambda x: x[0].lower())
        self.display_files()

    def sort_by_size(self):
        self.files.sort(key=lambda x: x[1])
        self.display_files()

if __name__ == "__main__":
    root = tk.Tk()
    app = FileManagerApp(root)
    root.mainloop()