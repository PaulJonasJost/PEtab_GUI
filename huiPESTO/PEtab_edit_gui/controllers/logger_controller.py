"""File containing the controller of the logger widget."""
from datetime import datetime


class LoggerController:
    """Mainly responsible for handling the logger widget."""

    def __init__(self, views):
        """Initialize the logger controller.

        Parameters
        ----------
        view: Logger
            The view of the logger widget.
        """
        self.views = views
        self.views[0].upload_data_matrix_button.hide()
        self.views[0].reset_to_original_button.show()
        self.views[1].upload_data_matrix_button.show()
        self.views[1].reset_to_original_button.hide()



    def log_message(self, message, color="black"):
        """Log a message to the logger.

        Parameters
        ----------
        message: str
            The message to log.
        color: str
            The color of the message. Default is black.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = \
            f"[{timestamp}]\t <span style='color: {color};'>{message}</span>"
        for view in self.views:
            view.logger.append(full_message)
