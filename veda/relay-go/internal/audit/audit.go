// Package audit implements an append-only, monthly-rotated audit log.
package audit

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// Entry is one audited event (docs/PROTOCOL.md > Audit).
type Entry struct {
	TS      time.Time `json:"ts"`
	Act     string    `json:"act"` // control.request, control.result, notify.send, pair, consent
	Source  string    `json:"source,omitempty"`
	Target  string    `json:"target,omitempty"`
	Action  string    `json:"action,omitempty"`
	Consent string    `json:"consent,omitempty"`
	Result  string    `json:"result,omitempty"`
	OK      bool      `json:"ok"`
}

// Logger appends JSONL entries to <dir>/<YYYYMM>.log and rotates monthly.
type Logger struct {
	dir  string
	mu   sync.Mutex
	f    *os.File
	iy   string // current file base, e.g. 202502.vec
	last time.Time
}

// New opens (creating if needed) the audit directory.
func New(dir string) (*Logger, error) {
	if err := os.MkdirAll(dir, 0o750); err != nil {
		return nil, err
	}
	l := &Logger{dir: dir}
	if err := l.rotate(time.Now()); err != nil {
		return nil, err
	}
	return l, nil
}

func (l *Logger) rotate(now time.Time) error {
	base := now.Format("200601") + ".log"
	if l.f != nil && l.last.Format("200601") == now.Format("200601") {
		return nil
	}
	if l.f != nil {
		_ = l.f.Close()
	}
	p := filepath.Join(l.dir, base)
	f, err := os.OpenFile(p, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o640)
	if err != nil {
		return err
	}
	l.f = f
	l.last = now
	return nil
}

// Write appends one entry atomically (line-buffered, fsynced best-effort).
func (l *Logger) Write(e Entry) error {
	l.mu.Lock()
	defer l.mu.Unlock()
	if err := l.rotate(time.Now()); err != nil {
		return err
	}
	if e.TS.IsZero() {
		e.TS = time.Now()
	}
	b, err := json.Marshal(e)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintf(l.f, "%s\n", b)
	if err != nil {
		return err
	}
	return l.f.Sync()
}

// Path returns the current log file path (for the dashboard dump endpoint).
func (l *Logger) Path() string {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.f != nil {
		return l.f.Name()
	}
	return ""
}

// Close flushes and closes the current log.
func (l *Logger) Close() error {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.f != nil {
		err := l.f.Sync()
		cerr := l.f.Close()
		l.f = nil
		if err != nil {
			return err
		}
		return cerr
	}
	return nil
}