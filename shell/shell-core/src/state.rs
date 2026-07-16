//! Shell runtime state — the supervised status of the Core process.
//!
//! [`ShellState`] is the host's small, in-memory record of *where the Core
//! process is* in its lifecycle and how many times it has been restarted. It is
//! deliberately a plain value holder in this increment: the transition *rules*
//! (which status may follow which, crash detection, health checks) belong to
//! the lifecycle layer added later. Keeping the state dumb lets the lifecycle
//! own the policy without fighting the data.

/// Lifecycle status of the supervised Core process.
///
/// The status is a coarse, observable state — fine-grained transition rules are
/// the lifecycle layer's job. It starts [`Stopped`](CoreStatus::Stopped): no
/// Core process exists until the host spawns one.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum CoreStatus {
    /// No Core process is running (initial state, or after a clean shutdown).
    #[default]
    Stopped,
    /// The Core process has been spawned but has not reported readiness.
    Starting,
    /// The Core process is up and answering the Core Channel.
    Running,
    /// The Core process is being replaced after a crash or an explicit restart.
    Restarting,
    /// The Core process exited unexpectedly and has not yet been restarted.
    Crashed,
}

impl CoreStatus {
    /// Whether the Core is in a state that can serve IPC requests.
    #[must_use]
    pub const fn is_serving(self) -> bool {
        matches!(self, Self::Running)
    }
}

/// The host's supervised view of the Core process.
///
/// Holds the current [`CoreStatus`] and a monotonic restart counter. Mutation
/// is intentionally explicit (`set_status`, `record_restart`) so the lifecycle
/// layer is the only place that decides *when* those calls happen.
#[derive(Debug, Clone, Default)]
pub struct ShellState {
    status: CoreStatus,
    restart_count: u32,
}

impl ShellState {
    /// A fresh state: [`Stopped`](CoreStatus::Stopped) with zero restarts.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// The current lifecycle status of the Core process.
    #[must_use]
    pub const fn status(&self) -> CoreStatus {
        self.status
    }

    /// How many times the Core process has been restarted so far.
    #[must_use]
    pub const fn restart_count(&self) -> u32 {
        self.restart_count
    }

    /// Whether the Core is currently able to serve IPC requests.
    #[must_use]
    pub const fn is_serving(&self) -> bool {
        self.status.is_serving()
    }

    /// Record a new lifecycle status for the Core process.
    pub fn set_status(&mut self, status: CoreStatus) {
        self.status = status;
    }

    /// Record that the Core process was restarted, bumping the counter.
    ///
    /// Saturates rather than overflowing: a supervisor that restarts billions of
    /// times has a problem the counter should not paper over with a panic.
    pub fn record_restart(&mut self) {
        self.restart_count = self.restart_count.saturating_add(1);
    }
}

/// The host window's observable state, tracked from Tauri window events.
///
/// A plain value model updated by the Tauri layer (from focus/visibility window
/// events) and read back by a command. It carries no window handle — the shell
/// core stays free of any Tauri/UI type — only the facts a command reports.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct WindowState {
    visible: bool,
    focused: bool,
}

impl Default for WindowState {
    /// A freshly created window: visible but not yet focused.
    fn default() -> Self {
        Self {
            visible: true,
            focused: false,
        }
    }
}

impl WindowState {
    /// Whether the window is currently shown.
    #[must_use]
    pub const fn is_visible(self) -> bool {
        self.visible
    }

    /// Whether the window currently has OS focus.
    #[must_use]
    pub const fn is_focused(self) -> bool {
        self.focused
    }

    /// Record a change in visibility (from a show/hide window event).
    pub fn set_visible(&mut self, visible: bool) {
        self.visible = visible;
    }

    /// Record a change in focus (from a focus/blur window event).
    ///
    /// Losing the window is safety-relevant: an unfocused window is the
    /// fail-safe cue for permission prompts (doc 24 §14) to fall back to deny.
    pub fn set_focused(&mut self, focused: bool) {
        self.focused = focused;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_state_is_stopped_with_no_restarts() {
        let state = ShellState::new();
        assert_eq!(state.status(), CoreStatus::Stopped);
        assert_eq!(state.restart_count(), 0);
        assert!(!state.is_serving());
    }

    #[test]
    fn only_running_status_serves() {
        assert!(CoreStatus::Running.is_serving());
        for status in [
            CoreStatus::Stopped,
            CoreStatus::Starting,
            CoreStatus::Restarting,
            CoreStatus::Crashed,
        ] {
            assert!(!status.is_serving());
        }
    }

    #[test]
    fn set_status_updates_serving_view() {
        let mut state = ShellState::new();
        state.set_status(CoreStatus::Running);
        assert_eq!(state.status(), CoreStatus::Running);
        assert!(state.is_serving());
    }

    #[test]
    fn record_restart_increments_counter() {
        let mut state = ShellState::new();
        state.record_restart();
        state.record_restart();
        assert_eq!(state.restart_count(), 2);
    }

    #[test]
    fn window_starts_visible_and_unfocused() {
        let window = WindowState::default();
        assert!(window.is_visible());
        assert!(!window.is_focused());
    }

    #[test]
    fn window_tracks_focus_and_visibility_changes() {
        let mut window = WindowState::default();
        window.set_focused(true);
        assert!(window.is_focused());
        window.set_visible(false);
        window.set_focused(false);
        assert!(!window.is_visible());
        assert!(!window.is_focused());
    }
}
