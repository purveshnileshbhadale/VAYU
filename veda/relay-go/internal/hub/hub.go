// Package hub owns the WebSocket layer: hello/auth, routing, notifications,
// and the control/consent state machine.
package hub

import (
	"encoding/json"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/audit"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/auth"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/message"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/policy"
)

// Conn is a live websocket with its authenticated identity (filled on hello).
type Conn struct {
	WS   *websocket.Conn
	ID   string // device or dashboard id
	Kind string // "device" | "dashboard"

	wmu sync.Mutex // gorilla/websocket forbids concurrent writes
}

// write serializes one message to the socket; safe from any goroutine.
func (c *Conn) write(mt int, raw []byte) error {
	c.wmu.Lock()
	defer c.wmu.Unlock()
	if c.WS == nil {
		return nil
	}
	_ = c.WS.SetWriteDeadline(time.Now().Add(5 * time.Second))
	return c.WS.WriteMessage(mt, raw)
}

// writeJSON marshals and writes an envelope atomically.
func (c *Conn) writeJSON(v any) error {
	raw, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return c.write(websocket.TextMessage, raw)
}

// Hub routes envelopes between authenticated peers.
type Hub struct {
	mu       sync.RWMutex
	sockets  map[*Conn]bool
	byID     map[string]*Conn
	sess     *auth.Sessions
	consents map[string]chan bool
	logx     *audit.Logger
}

// New returns a ready hub bound to the given session store.
func New(sess *auth.Sessions) *Hub {
	return &Hub{
		sockets:  map[*Conn]bool{},
		byID:     map[string]*Conn{},
		sess:     sess,
		consents: map[string]chan bool{},
	}
}

// SetLogger attaches an audit logger to the hub.
func (h *Hub) SetLogger(l *audit.Logger) { h.logx = l }

func (h *Hub) log(e audit.Entry) {
	if h.logx != nil {
		_ = h.logx.Write(e)
	}
}

// Register claims a socket before auth.
func (h *Hub) Register(ws *websocket.Conn, kind string) *Conn {
	c := &Conn{WS: ws, Kind: kind}
	h.mu.Lock()
	h.sockets[c] = true
	h.mu.Unlock()
	return c
}

// Drop removes a connection and broadcasts presence offline for devices.
func (h *Hub) Drop(c *Conn) {
	h.mu.Lock()
	if _, ok := h.sockets[c]; !ok {
		h.mu.Unlock()
		return
	}
	delete(h.sockets, c)
	id := c.ID
	if id != "" {
		delete(h.byID, id)
	}
	h.mu.Unlock()
	if id != "" && c.Kind == "device" {
		h.log(audit.Entry{Act: "presence.off", Source: id, Result: "offline", OK: true})
	}
	_ = c.WS.Close()
}

// send writes an envelope to one known peer (no-op if offline).
func (h *Hub) send(to string, e message.Envelope) {
	raw, err := json.Marshal(e)
	if err != nil {
		return
	}
	h.mu.RLock()
	c, ok := h.byID[to]
	h.mu.RUnlock()
	if !ok {
		return
	}
	_ = c.write(websocket.TextMessage, raw)
}

// broadcast sends to every device connection (not dashboards).
func (h *Hub) broadcast(e message.Envelope) {
	raw, err := json.Marshal(e)
	if err != nil {
		return
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, c := range h.byID {
		_ = c.write(websocket.TextMessage, raw)
	}
}

// Handle routes one incoming envelope from a connection.
func (h *Hub) Handle(c *Conn, e message.Envelope) {
	switch e.Type {
	case "hello":
		h.onHello(c, e)
	case "status":
		h.onStatus(c, e)
	case "notify.request":
		h.onNotify(c, e)
	case "notify.dismiss":
		h.onNotifyDismiss(c, e)
	case "control.request":
		h.onControlRequest(c, e)
	case "control.consent.result":
		h.onConsentResult(c, e)
	case "control.result":
		h.onControlResult(c, e)
	}
}

func (h *Hub) onHello(c *Conn, e message.Envelope) {
	var hb message.Hello
	if err := json.Unmarshal(e.Body, &hb); err != nil { return }
	if !h.sess.VerifyToken(hb.Token) {
		h.send(e.From, message.Envelope{V: 1, To: e.From, Type: "fault", Body: rw(message.Fault{Code: "401", Fault: "bad_token"})})
		return
	}
	d := h.sess.RegisterDevice(hb.Device)
	h.mu.Lock()
	c.ID = d.ID
	c.Kind = "device"
	h.byID[d.ID] = c
	h.mu.Unlock()
	h.sess.Attach(d.ID, auth.Token(16))
	h.send(d.ID, message.Envelope{V: 1, To: d.ID, Type: "hello.ack", Body: rw(message.HelloAck{Device: d, Devices: h.sess.Devices()})})
	h.broadcast(message.Envelope{V: 1, Type: "presence", Body: rw(message.Presence{Device: d, Online: true})})
	h.log(audit.Entry{Act: "hello", Source: d.ID, Result: "ok", OK: true})
}

func (h *Hub) onStatus(c *Conn, e message.Envelope) {
	var s message.Status
	if err := json.Unmarshal(e.Body, &s); err != nil { return }
	h.log(audit.Entry{Act: "status", Source: c.ID, Result: "ok", OK: true})
	_ = s
}

func (h *Hub) onNotify(c *Conn, e message.Envelope) {
	var n message.Notify
	if err := json.Unmarshal(e.Body, &n); err != nil { return }
	h.log(audit.Entry{Act: "notify.send", Source: c.ID, Target: e.To, Result: n.Title, OK: true})
	if e.To == "*" {
		h.broadcast(message.Envelope{V: 1, Type: "notify.push", From: c.ID, Body: rw(n)})
	} else {
		h.send(e.To, message.Envelope{V: 1, Type: "notify.push", From: c.ID, Body: rw(n)})
	}
}

func (h *Hub) onNotifyDismiss(c *Conn, e message.Envelope) {
	var d message.Dismiss
	if err := json.Unmarshal(e.Body, &d); err != nil { return }
	h.broadcast(message.Envelope{V: 1, Type: "notify.dismiss", From: c.ID, Body: rw(d)})
}

func (h *Hub) onControlRequest(c *Conn, e message.Envelope) {
	var req message.ControlRequest
	if err := json.Unmarshal(e.Body, &req); err != nil { return }
	a := policy.Lookup(req.Action)
	if a == nil {
		h.send(e.From, message.Envelope{V: 1, To: e.From, Type: "fault", Body: rw(message.Fault{Code: "400", Fault: "unknown_action", Msg: req.Action})})
		return
	}
	if req.Consent != "granted" && a.Critical {
		h.onConsentGate(c, e, req)
		return
	}
	h.dispatch(c, e, req, "granted")
}

// onConsentGate asks the target to approve a critical action before dispatch.
func (h *Hub) onConsentGate(c *Conn, e message.Envelope, req message.ControlRequest) {
	ch := make(chan bool, 1)
	h.mu.Lock()
	h.consents[req.ControlID] = ch
	h.mu.Unlock()
	h.log(audit.Entry{Act: "control.consent.request", Source: c.ID, Target: e.To, Action: req.Action, OK: false})
	h.send(e.To, message.Envelope{V: 1, Type: "control.consent.request", From: c.ID, Body: rw(message.ConsentRequest{ControlID: req.ControlID, Action: req.Action, Source: c.ID})})
	select {
	case ok := <-ch:
		if !ok {
			h.send(e.From, message.Envelope{V: 1, To: e.From, Type: "control.result", Body: rw(message.ControlResult{ControlID: req.ControlID, OK: false, Error: "consent denied"})})
			return
		}
		h.dispatch(c, e, req, "granted")
	case <-time.After(30 * time.Second):
		h.mu.Lock()
		delete(h.consents, req.ControlID)
		h.mu.Unlock()
		h.send(e.From, message.Envelope{V: 1, To: e.From, Type: "control.result", Body: rw(message.ControlResult{ControlID: req.ControlID, OK: false, Error: "consent timeout"})})
	}
}

func (h *Hub) dispatch(c *Conn, e message.Envelope, req message.ControlRequest, consent string) {
	h.log(audit.Entry{Act: "control.request", Source: c.ID, Target: e.To, Action: req.Action, Consent: consent, OK: true})
	h.send(e.To, message.Envelope{V: 1, Type: "control.request", From: c.ID,
		Body: rw(message.ControlRequest{ControlID: req.ControlID, Action: req.Action, Args: req.Args, Permission: req.Permission, Consent: consent})})
}

func (h *Hub) onConsentResult(c *Conn, e message.Envelope) {
	var r message.ConsentResult
	if err := json.Unmarshal(e.Body, &r); err != nil { return }
	h.mu.Lock()
	ch, ok := h.consents[r.ControlID]
	delete(h.consents, r.ControlID)
	h.mu.Unlock()
	if ok {
		h.log(audit.Entry{Act: "control.consent.result", Source: c.ID, Target: r.ControlID, OK: r.OK})
		ch <- r.OK
	}
}

func (h *Hub) onControlResult(c *Conn, e message.Envelope) {
	var r message.ControlResult
	if err := json.Unmarshal(e.Body, &r); err != nil { return }
	h.log(audit.Entry{Act: "control.result", Source: c.ID, Action: r.ControlID, Result: r.Error, OK: r.OK})
	h.send(e.To, message.Envelope{V: 1, To: e.To, Type: "control.result", From: c.ID, Body: rw(r)})
}

// rw wraps a value into a json.RawMessage for envelope bodies.
func rw(v any) json.RawMessage {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	return b
}