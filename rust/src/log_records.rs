/// A message for the Python layer to log, as Rust can't use Python's `logging` directly.
#[derive(Debug)]
pub struct LogRecord {
    /// The name of the Python logger to log to.
    pub logger: &'static str,
    /// The name of the method of the logger to call, e.g. "info" or "warning".
    pub level: &'static str,
    pub message: String,
}

impl LogRecord {
    pub fn info(logger: &'static str, message: String) -> Self {
        Self {
            logger,
            level: "info",
            message,
        }
    }

    pub fn warning(logger: &'static str, message: String) -> Self {
        Self {
            logger,
            level: "warning",
            message,
        }
    }
}
