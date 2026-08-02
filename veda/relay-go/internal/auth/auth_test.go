package auth

import (
	"testing"
	"time"

	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/message"
)

func device(id, platform string) message.Device {
	return message.Device{ID: id, Name: id, Platform: platform}
}

func TestTokenDeterministicAndHashable(t *testing.T) {
	a := Token(16)
	b := Token(16)
	if a == "" || b == "" {
		t.Fatal("expected non-empty tokens")
	}
	if a == b {
		t.Fatal("tokens should be unique")
	}
	if Hash(a) == a {
		t.Fatal("hash must not equal plaintext")
	}
	if Hash(a) == Hash(b) {
		t.Fatal("distinct tokens hashed equal")
	}
}

func TestIssueVerifyRevoke(t *testing.T) {
	s := New()
	tok := Token(16)
	if s.VerifyToken(tok) {
		t.Fatal("unissued token must not verify")
	}
	s.IssueToken(tok)
	if !s.VerifyToken(tok) {
		t.Fatal("issued token should verify")
	}
	s.RevokeToken(tok)
	if s.VerifyToken(tok) {
		t.Fatal("revoked token must fail")
	}
	if s.VerifyToken("") {
		t.Fatal("empty token must fail")
	}
}

func TestRegisterAndAttach(t *testing.T) {
	s := New()
	d := s.RegisterDevice(device("d1", "windows"))
	if d.ID == "" {
		t.Fatal("expected assigned id")
	}
	s.RegisterDevice(device("d1", "windows"))
	if got := len(s.Devices()); got != 1 {
		t.Fatalf("expected 1 device, got %d", got)
	}
	if s.IsPaired("d1") {
		t.Fatal("unknown pairing must be false")
	}
	s.BindPair("d1")
	if !s.IsPaired("d1") {
		t.Fatal("paired device should be paired")
	}
	s.Attach("d1", "sess-1")
	if s.DeviceFor("sess-1") != "d1" {
		t.Fatal("session lookup mismatch")
	}
	s.Detach("d1")
	if s.DeviceFor("sess-1") != "" {
		t.Fatal("detached session still resolves")
	}
}

func TestRateLimit(t *testing.T) {
	r := NewRateLimit(time.Minute, 5)
	for i := 0; i < 5; i++ {
		r.Allow("x") // drain
	}
	if r.Allow("x") {
		t.Fatal("limit should be exhausted")
	}
	if !r.Allow("y") {
		t.Fatal("other key should be unaffected")
	}
}