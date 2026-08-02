// Package message defines the VEDA wire contract (docs/PROTOCOL.md).
package message

import "encoding/json"

// Envelope wraps every WebSocket text message.
type Envelope struct {
	V    int             `json:"v"`
	Type string          `json:"type"`
	From string          `json:"from"`
	To   string          `json:"to,omitempty"`
	ID   string          `json:"id,omitempty"`
	TS   string          `json:"ts,omitempty"`
	Auth string          `json:"auth,omitempty"`
	Body json.RawMessage `json:"body,omitempty"`
}

// Body types follow PROTOCOL.md v1.
type Hello struct {
	Token  string `json:"token"`
	Device Device `json:"device"`
}

type Device struct {
	ID           string   `json:"id"`
	Name         string   `json:"name"`
	Platform     string   `json:"platform"` // windows|macos|linux|android|ios|raspberry|tv|iot
	OS           string   `json:"os,omitempty"`
	Version      string   `json:"version,omitempty"`
	Capabilities []string `json:"capabilities"`
}

type HelloAck struct {
	Device  Device   `json:"device"`
	Devices []Device `json:"devices"`
}

type Status struct {
	CPU      float64 `json:"cpu,omitempty"`
	RAM      float64 `json:"ram,omitempty"`
	Disk     float64 `json:"disk,omitempty"`
	Battery  *int    `json:"battery,omitempty"`
	Temp     float64 `json:"temp,omitempty"`
	Fans     int     `json:"fans,omitempty"`
	Net      string  `json:"net,omitempty"`
	Running  string  `json:"app,omitempty"`
	ClipText string  `json:"clipboard,omitempty"`
	TS       string  `json:"ts,omitempty"`
}

type Presence struct {
	Device Device `json:"device"`
	Online bool   `json:"online"`
}

type Notify struct {
	Title    string `json:"title"`
	Body     string `json:"body"`
	App      string `json:"app,omitempty"`
	Priority int    `json:"priority,omitempty"` // 0 default, 1 high, 2 critical
	Tags     string `json:"tags,omitempty"`
}

type NotifyAck struct {
	InstanceID string `json:"instanceId"`
}

type Dismiss struct {
	InstanceID string `json:"instanceId"`
}

type ControlRequest struct {
	ControlID  string   `json:"controlId"`
	Action     string   `json:"action"` // open_app, lock, sleep, restart, shutdown, set_volume, send_notify, run_command
	Args       struct {
		App      string `json:"app,omitempty"`
		AppPath  string `json:"appPath,omitempty"`
		URL      string `json:"url,omitempty"`
		Volume   int    `json:"volume,omitempty"`
		Command  string `json:"command,omitempty"`
		Title    string `json:"title,omitempty"`
		Body     string `json:"body,omitempty"`
		Seconds  int    `json:"seconds,omitempty"`
	}    `json:"args"`
	Permission string `json:"permission"`
	Consent    string   `json:"consent"` // requested|accepted|denied
}

type ConsentRequest struct {
	ControlID string `json:"controlId"`
	Action    string `json:"action"`
	Source    string `json:"source"`
	Seconds   int    `json:"seconds,omitempty"`
}

type ConsentResult struct {
	ControlID string `json:"controlId"`
	OK        bool   `json:"ok"`
}

type ControlResult struct {
	ControlID string `json:"controlId"`
	OK        bool   `json:"ok"`
	Data      string `json:"data,omitempty"`
	Error     string `json:"error,omitempty"`
}

// Terminal — confirmation gated; runs under the user's own shell identity.
type TerminalRequest struct {
	Command string `json:"command"`
}
type TerminalResult struct {
	OK    bool   `json:"ok"`
	Exit  int    `json:"exit,omitempty"`
	Stdout string `json:"stdout,omitempty"`
	Stderr string `json:"stderr,omitempty"`
}

// Clipboard / files stubs for v2 (E2E layer).
type ClipboardPaste struct {
	Kind string `json:"kind"` // text|image|file
	Data string `json:"data,omitempty"`
}
type FileTransfer struct {
	Name string `json:"name"`
	Size int64  `json:"size"`
}

// Error maps to 401/403/429/503 fault types.
type Fault struct {
	Code  string `json:"code"`
	Fault string `json:"fault"`
	Msg   string `json:"msg,omitempty"`
}