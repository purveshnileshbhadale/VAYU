package hub_test

import (
	"context"
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/auth"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/hub"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/message"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/server"
)

const claimToken = "test-claim-token"

// relay boots a hub + listener on an ephemeral-ish port and returns its ws URL.
func relay(t *testing.T, addr string) string {
	t.Helper()
	sess := auth.New()
	sess.IssueToken(claimToken)
	h := hub.New(sess)
	srv := server.New(server.Opts{Listen: addr}, h, nil)
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	go func() { _ = srv.Run(ctx) }()

	url := "ws://" + addr + "/ws"
	// Wait for the listener rather than sleeping a fixed interval.
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if r, err := http.Get("http://" + addr + "/healthz"); err == nil {
			r.Body.Close()
			return url
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("relay on %s never came up", addr)
	return url
}

func dial(t *testing.T, url string) *websocket.Conn {
	t.Helper()
	c, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		t.Fatalf("dial %s: %v", url, err)
	}
	t.Cleanup(func() { c.Close() })
	return c
}

// register completes a valid hello and drains the resulting ack + presence.
func register(t *testing.T, url, id string) *websocket.Conn {
	t.Helper()
	c := dial(t, url)
	err := c.WriteJSON(map[string]any{
		"v": 1, "type": "hello", "from": id,
		"body": map[string]any{
			"token": claimToken,
			"device": map[string]any{
				"id": id, "name": id, "platform": "linux",
				"capabilities": []string{"terminal", "system.shutdown"},
			},
		},
	})
	if err != nil {
		t.Fatalf("hello: %v", err)
	}
	if got := readType(t, c, 2*time.Second); got != "hello.ack" {
		t.Fatalf("expected hello.ack, got %q", got)
	}
	return c
}

// readType returns the envelope type of the next message ("" on timeout).
func readType(t *testing.T, c *websocket.Conn, wait time.Duration) string {
	t.Helper()
	env, _ := read(t, c, wait)
	return env.Type
}

// read returns the next envelope and its raw bytes ("" type on timeout).
func read(t *testing.T, c *websocket.Conn, wait time.Duration) (message.Envelope, []byte) {
	t.Helper()
	_ = c.SetReadDeadline(time.Now().Add(wait))
	_, raw, err := c.ReadMessage()
	if err != nil {
		return message.Envelope{}, nil
	}
	var env message.Envelope
	_ = json.Unmarshal(raw, &env)
	return env, raw
}

// await drains messages until one of the wanted types arrives, or time runs out.
func await(t *testing.T, c *websocket.Conn, wait time.Duration, wanted ...string) message.Envelope {
	t.Helper()
	deadline := time.Now().Add(wait)
	for time.Now().Before(deadline) {
		env, raw := read(t, c, time.Until(deadline))
		if raw == nil {
			break
		}
		for _, w := range wanted {
			if env.Type == w {
				return env
			}
		}
	}
	return message.Envelope{}
}

func control(id, to, action, consent string) map[string]any {
	return map[string]any{
		"v": 1, "type": "control.request", "from": id, "to": to,
		"body": map[string]any{
			"controlId": id, "action": action,
			"args": map[string]any{"command": "echo pwned"}, "consent": consent,
		},
	}
}

// An unauthenticated socket must not be able to route anything. This is the
// exact shape of the reported unauthenticated-RCE chain: connect, skip hello,
// address a control request straight at a registered device.
func TestUnauthenticatedSocketCannotReachDevice(t *testing.T) {
	url := relay(t, "127.0.0.1:18131")
	victim := register(t, url, "laptop-1")
	await(t, victim, 500*time.Millisecond, "presence") // drain own presence

	attacker := dial(t, url)
	if err := attacker.WriteJSON(control("evil-1", "laptop-1", "run_command", "granted")); err != nil {
		t.Fatal(err)
	}

	if env := await(t, attacker, 2*time.Second, "fault"); env.Type != "fault" {
		t.Error("attacker should have been told it is unauthenticated")
	}
	if env := await(t, victim, 1500*time.Millisecond, "control.request", "control.consent.request"); env.Type != "" {
		t.Errorf("victim reachable from an unauthenticated socket: got %q", env.Type)
	}
}

// A device that authenticated is still not allowed to declare its own consent
// for a critical action; the relay must gate on the policy table alone.
func TestSelfDeclaredConsentDoesNotSkipTheGate(t *testing.T) {
	url := relay(t, "127.0.0.1:18132")
	victim := register(t, url, "laptop-2")
	caller := register(t, url, "phone-2")
	await(t, victim, 500*time.Millisecond, "presence")
	await(t, caller, 500*time.Millisecond, "presence")

	if err := caller.WriteJSON(control("evil-2", "laptop-2", "run_command", "granted")); err != nil {
		t.Fatal(err)
	}

	env := await(t, victim, 2*time.Second, "control.request", "control.consent.request")
	switch env.Type {
	case "control.consent.request":
		// correct: the target is asked before anything executes
	case "control.request":
		t.Error("critical action dispatched without a consent prompt")
	default:
		t.Error("target received neither a consent prompt nor a request")
	}
}

// Only the device that was asked may answer a consent prompt.
func TestThirdPartyCannotAnswerConsent(t *testing.T) {
	url := relay(t, "127.0.0.1:18133")
	victim := register(t, url, "laptop-3")
	caller := register(t, url, "phone-3")
	bystander := register(t, url, "tablet-3")
	for _, c := range []*websocket.Conn{victim, caller, bystander} {
		await(t, c, 500*time.Millisecond, "presence")
	}

	if err := caller.WriteJSON(control("evil-3", "laptop-3", "shutdown", "")); err != nil {
		t.Fatal(err)
	}
	if env := await(t, victim, 2*time.Second, "control.consent.request"); env.Type == "" {
		t.Fatal("victim never got the consent prompt")
	}

	// The bystander tries to approve a prompt addressed to the victim.
	err := bystander.WriteJSON(map[string]any{
		"v": 1, "type": "control.consent.result", "from": "tablet-3",
		"body": map[string]any{"controlId": "evil-3", "ok": true},
	})
	if err != nil {
		t.Fatal(err)
	}

	if env := await(t, victim, 1500*time.Millisecond, "control.request"); env.Type != "" {
		t.Error("a third party's approval released the action")
	}
}

// Non-critical actions still flow without a prompt, and are marked as such.
func TestNonCriticalActionDispatchesDirectly(t *testing.T) {
	url := relay(t, "127.0.0.1:18134")
	victim := register(t, url, "laptop-4")
	caller := register(t, url, "phone-4")
	await(t, victim, 500*time.Millisecond, "presence")
	await(t, caller, 500*time.Millisecond, "presence")

	if err := caller.WriteJSON(control("ok-4", "laptop-4", "set_volume", "")); err != nil {
		t.Fatal(err)
	}

	env := await(t, victim, 2*time.Second, "control.request")
	if env.Type != "control.request" {
		t.Fatal("non-critical action never arrived")
	}
	var req message.ControlRequest
	if err := json.Unmarshal(env.Body, &req); err != nil {
		t.Fatal(err)
	}
	if req.Consent != "none" {
		t.Errorf("consent = %q, want %q", req.Consent, "none")
	}
	if env.From != "phone-4" {
		t.Errorf("From = %q, want the sender's authenticated id", env.From)
	}
}

// A bad token must produce a fault the client can actually see.
func TestBadTokenIsReported(t *testing.T) {
	url := relay(t, "127.0.0.1:18135")
	c := dial(t, url)
	err := c.WriteJSON(map[string]any{
		"v": 1, "type": "hello", "from": "rogue",
		"body": map[string]any{
			"token":  "wrong-token",
			"device": map[string]any{"id": "rogue", "name": "rogue", "platform": "linux"},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	env := await(t, c, 2*time.Second, "fault")
	if env.Type != "fault" {
		t.Fatal("rejected client received nothing at all")
	}
	var f message.Fault
	if err := json.Unmarshal(env.Body, &f); err != nil {
		t.Fatal(err)
	}
	if f.Fault != "bad_token" {
		t.Errorf("fault = %q, want bad_token", f.Fault)
	}
}
