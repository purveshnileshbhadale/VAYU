// Package policy maps control actions to required capabilities and consent
// strength. This is the single source of truth the hub checks before routing
// any control.request.
package policy

// Action describes how a control action is allowed to proceed.
type Action struct {
	Permission string // capability name, e.g. apps.open
	Consent    string // "none" | "session" | "confirm"
	Critical   bool   // dangerous actions require consent.prompt regardless
}

// Table of every action the relay understands in v1.
var Table = map[string]Action{
	"open_app":    {Permission: "apps.open", Consent: "session"},
	"lock":        {Permission: "system.lock", Consent: "session"},
	"sleep":       {Permission: "system.sleep", Consent: "session"},
	"restart":     {Permission: "system.restart", Consent: "confirm", Critical: true},
	"shutdown":    {Permission: "system.shutdown", Consent: "confirm", Critical: true},
	"set_volume":  {Permission: "media.master", Consent: "none"},
	"send_notify": {Permission: "notify.send", Consent: "none"},
	"run_command": {Permission: "terminal", Consent: "confirm", Critical: true},
}

// Lookup returns nil for unknown action names.
func Lookup(action string) *Action {
	a, ok := Table[action]
	if !ok {
		return nil
	}
	return &a
}

// RequiresConfirm reports whether consent must be confirmed at execution time.
func RequiresConfirm(action string) bool {
	a := Lookup(action)
	return a != nil && (a.Consent == "confirm" || a.Critical)
}

// PermissionFor returns the capability name ("" if unknown).
func PermissionFor(action string) string {
	a := Lookup(action)
	if a == nil {
		return ""
	}
	return a.Permission
}

// deviceCapabilities are the reference lists a device agent must register.
var deviceCapabilities = []string{
	"apps.open", "system.lock", "system.sleep", "system.restart",
	"system.shutdown", "media.master", "notify.send", "terminal",
	"clipboard.paste", "files.transfer",
}

// DeviceCapabilities is the canonical capability set agents advertise.
func DeviceCapabilities() []string {
	out := make([]string, len(deviceCapabilities))
	copy(out, deviceCapabilities)
	return out
}