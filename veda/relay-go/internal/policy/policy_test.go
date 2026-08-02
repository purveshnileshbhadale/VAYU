package policy

import "testing"

func TestActionTable(t *testing.T) {
	cases := []struct {
		action string
		perm   string
		want   *Action
	}{
		{"open_app", "apps.open", nil},
		{"lock", "system.lock", nil},
		{"sleep", "system.sleep", nil},
		{"restart", "system.restart", &Action{Consent: "confirm", Critical: true}},
		{"shutdown", "system.shutdown", &Action{Consent: "confirm", Critical: true}},
		{"set_volume", "media.master", nil},
		{"send_notify", "notify.send", nil},
		{"run_command", "terminal", &Action{Consent: "confirm", Critical: true}},
	}
	for _, c := range cases {
		a := Lookup(c.action)
		if a == nil {
			t.Fatalf("action %q not in table", c.action)
		}
		if a.Permission != c.perm {
			t.Errorf("%s: perm %s != %s", c.action, a.Permission, c.perm)
		}
		if c.want != nil {
			if !a.Critical || a.Consent != "confirm" {
				t.Errorf("%s: expected critical+confirm, got critical=%v consent=%s", c.action, a.Critical, a.Consent)
			}
		}
	}
	if Lookup("nonsense") != nil {
		t.Fatal("unknown action must return nil")
	}
}

func TestRequiresConfirm(t *testing.T) {
	if RequiresConfirm("run_command") != true {
		t.Fatal("terminal must require confirm")
	}
	if RequiresConfirm("open_app") {
		t.Fatal("open_app must not require confirm")
	}
	if RequiresConfirm("bogus") {
		t.Fatal("unknown action must not require confirm")
	}
}

func TestCapabilitySet(t *testing.T) {
	caps := DeviceCapabilities()
	seen := map[string]bool{}
	for _, c := range caps {
		if seen[c] {
			t.Fatalf("dup capability %s", c)
		}
		seen[c] = true
	}
	if !seen["apps.open"] || !seen["terminal"] {
		t.Fatal("missing core capabilities")
	}
}