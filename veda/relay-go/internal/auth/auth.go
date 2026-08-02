// Package auth handles pairing tokens, session tokens and at-rest hashing.
package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"sync"
	"time"

	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/message"
)

// Sessions tracks authenticated device connections.
type Sessions struct {
	mu       sync.RWMutex
	active   map[string]string        // deviceID -> session token
	deviceBy map[string]string        // session token -> deviceID
	registry map[string]message.Device // deviceID -> device metadata
	bound    map[string]bool          // deviceID -> paired with an owner
	tokens   map[string]bool          // hashed hello/pair tokens
}

// New creates a session store keyed by device id.
func New() *Sessions {
	return &Sessions{
		active:   map[string]string{},
		deviceBy: map[string]string{},
		registry: map[string]message.Device{},
		bound:    map[string]bool{},
		tokens:   map[string]bool{},
	}
}

// Token generates a cryptographically-random URL-safe token (n bytes).
func Token(n int) string {
	if n <= 0 {
		n = 32
	}
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic("auth: crypto/rand failed: " + err.Error())
	}
	return base64.RawURLEncoding.EncodeToString(b)
}

// Hash returns the hex SHA-256 of t (used for opaque tokens at rest).
func Hash(t string) string {
	s := sha256.Sum256([]byte(t))
	return hex.EncodeToString(s[:])
}

// IssueToken registers a hello/pairing token that a device may present.
func (s *Sessions) IssueToken(t string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tokens[Hash(t)] = true
}

// VerifyToken reports whether an issued (un-revoked) token matches.
func (s *Sessions) VerifyToken(t string) bool {
	if t == "" {
		return false
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.tokens[Hash(t)]
}

// RevokeToken removes a token so it can no longer be used.
func (s *Sessions) RevokeToken(t string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.tokens, Hash(t))
}

// BindPair marks a device as paired with the owner. Only paired devices may
// control or be controlled.
func (s *Sessions) BindPair(deviceID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.bound[deviceID] = true
}

// IsPaired reports whether deviceID has completed pairing.
func (s *Sessions) IsPaired(deviceID string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.bound[deviceID]
}

// RegisterDevice upserts device metadata and returns the device.
func (s *Sessions) RegisterDevice(d message.Device) message.Device {
	s.mu.Lock()
	defer s.mu.Unlock()
	if d.ID == "" {
		d.ID = Token(12)
	}
	once := s.registry[d.ID]
	if once.ID != "" {
		// keep existing bound flag; update live metadata
		once.Name = d.Name
		once.Platform = d.Platform
		once.OS = d.OS
		once.Version = d.Version
		once.Capabilities = d.Capabilities
		s.registry[d.ID] = once
		return once
	}
	s.registry[d.ID] = d
	return d
}

// Attach binds a session token to a device id (after hello auth succeeded).
func (s *Sessions) Attach(deviceID, token string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.active[deviceID] = token
	s.deviceBy[token] = deviceID
}

// Detach drops a session for deviceID (on disconnect/rotate).
func (s *Sessions) Detach(deviceID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if t, ok := s.active[deviceID]; ok {
		delete(s.deviceBy, t)
	}
	delete(s.active, deviceID)
}

// DeviceFor returns the device id bound to a session token ("" if unknown).
func (s *Sessions) DeviceFor(token string) string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.deviceBy[token]
}

// Devices returns the registry snapshot.
func (s *Sessions) Devices() []message.Device {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]message.Device, 0, len(s.registry))
	for _, d := range s.registry {
		out = append(out, d)
	}
	return out
}

// Lookup resolves a device id to metadata (false if unknown).
func (s *Sessions) Lookup(id string) (message.Device, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	d, ok := s.registry[id]
	return d, ok
}

// RateLimit is a trivial fixed-window limiter for handshake/consent spam.
type RateLimit struct {
	mu    sync.Mutex
	hits  map[string]int
	win   time.Duration
	max   int
	epoch time.Time
}

// NewRateLimit keeps n attempts per window w per key.
func NewRateLimit(w time.Duration, n int) *RateLimit {
	return &RateLimit{hits: map[string]int{}, win: w, max: n}
}

// Allow reports true if key still has budget in the current window.
func (r *RateLimit) Allow(key string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	now := time.Now()
	if now.Sub(r.epoch) >= r.win {
		r.epoch = now
		r.hits = map[string]int{}
	}
	r.hits[key]++
	return r.hits[key] <= r.max
}