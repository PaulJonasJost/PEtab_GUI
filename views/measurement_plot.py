"""File containing the measurement plot widget."""
from PySide6.QtWidgets import QDockWidget, QVBoxLayout, QWidget
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
import matplotlib.pyplot as plt
from ..utils import PlotWidget

class MeasuremenPlotter(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Data Plot", parent)

        # Set up the widget to hold the plot and toolbar
        dock_widget = QWidget(self)
        layout = QVBoxLayout(dock_widget)

        # Create the plot widget
        self.plot_widget = PlotWidget()

        # Create the navigation toolbar for matplotlib
        toolbar = NavigationToolbar2QT(self.plot_widget, parent)

        # Add the toolbar and the plot widget to the layout
        layout.addWidget(toolbar)
        layout.addWidget(self.plot_widget)

        # Set the layout to the dock widget's widget
        dock_widget.setLayout(layout)
        self.setWidget(dock_widget)

    def update_visualization(self, plot_data=None):
        """Update the plot with new data."""
        self.plot_widget.axes.cla()
        color_map = plt.get_cmap("tab10")
        handles = []  # List to store handles for legend
        labels = []  # List to store labels for legend

        # Plot all data points with lower alpha for unselected points
        for idx, data in enumerate(plot_data["all_data"]):
            color = color_map(idx)
            handle, = self.plot_widget.axes.plot(
                data["x"], data["y"], 'o--',
                color=color, alpha=0.5,
                label=data["observable_id"]
            )
            handles.append(handle)
            labels.append(data["observable_id"])

        # Plot selected points with full alpha
        for idx, (observable_id, points) in enumerate(plot_data["selected_points"].items()):
            color = color_map(idx)
            selected_x = [point["x"] for point in points]
            selected_y = [point["y"] for point in points]
            selected_handle, = self.plot_widget.axes.plot(
                selected_x,
                selected_y, 'o',
                color=color, alpha=1,
                label=f"{observable_id} (selected)"
            )
            handles.append(selected_handle)
            labels.append(f"{observable_id} (selected)")

        # Add legend
        self.plot_widget.axes.legend(handles=handles, labels=labels)
        self.plot_widget.draw()