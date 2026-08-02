// Package server wires the HTTP listener: /healthz, /audit, /ws.
package server

import (
	"bufio"
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gorilla/websocket"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/audit"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/hub"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/message"
)

// Opts are the relay listener options.
type Opts struct {
	Listen         string // e.g. ":8080"
	TLSCert        string // "" = TLS off
	TLSKey         string
	StaticDir      string // dashboard files served at /
	DashboardToken string // bearer token required for /audit
}

// Server assembles the HTTP + WS gateway.
type Server struct {
	hub  *hub.Hub
	log  *audit.Logger
	opts Opts
}

// New returns a Server bound to a hub, logger and options.
func New(o Opts, ge *hub.Hub, al *audit.Logger) *Server {
	if o.Listen == "" {
		o.Listen = ":8080"
	}
	if o.StaticDir == "" {
		o.StaticDir = ".ui"
	}
	return &Server{hub: ge, log: al, opts: o}
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true }, // tokens gate access; tighten for prod
}

func (s *Server) wsHandler(w http.ResponseWriter, r *http.Request) {
	kind := "device"
	if r.URL.Query().Get("kind") == "dashboard" {
		kind = "dashboard"
	}
	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("ws upgrade: %v", err)
		return
	}
	c := s.hub.Register(ws, kind)
	defer s.hub.Drop(c)
	for {
		var e message.Envelope
		if err := ws.ReadJSON(&e); err != nil {
			return
		}
		s.hub.Handle(c, e)
	}
}

func (s *Server) auditHandler(w http.ResponseWriter, r *http.Request) {
	if s.opts.DashboardToken == "" || r.Header.Get("Authorization") != "Bearer "+s.opts.DashboardToken {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"fault":"unauthorized"}`))
		return
	}
	entries, err := readAudit(s.log.Path())
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(entries)
}

func healthHandler(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

// Run serves until ctx is cancelled.
func (s *Server) Run(ctx context.Context) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/ws", s.wsHandler)
	mux.HandleFunc("/healthz", healthHandler)
	if s.opts.DashboardToken != "" {
		mux.HandleFunc("/audit", s.auditHandler)
	}
	if s.opts.StaticDir != ".ui" || dirExists(s.opts.StaticDir) {
		mux.Handle("/", http.FileServer(http.Dir(s.opts.StaticDir)))
	} else {
		mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
			_, _ = w.Write([]byte("VEDA relay — serve the dashboard with --ui <dist>."))
		})
	}

	srv := &http.Server{
		Addr: s.opts.Listen, Handler: mux,
		ReadTimeout: 30 * time.Second, WriteTimeout: 30 * time.Second,
	}
	go func() {
		<-ctx.Done()
		shCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shCtx)
	}()

	if s.opts.TLSCert != "" {
		srv.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS13}
		log.Printf("VEDA relay TLS1.3 on %s", s.opts.Listen)
		return srv.ListenAndServeTLS(s.opts.TLSCert, s.opts.TLSKey)
	}
	log.Printf("VEDA relay listening on %s", s.opts.Listen)
	return srv.ListenAndServe()
}

func dirExists(p string) bool {
	st, err := os.Stat(p)
	return err == nil && st.IsDir()
}

// readAudit parses the JSONL audit file into entries.
func readAudit(path string) ([]audit.Entry, error) {
	out := []audit.Entry{}
	b, err := os.ReadFile(path)
	if err != nil {
		return out, nil // no audit yet is fine
	}
	sc := bufio.NewScanner(bytes.NewReader(b))
	for sc.Scan() {
		line := sc.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			continue
		}
		var e audit.Entry
		if json.Unmarshal(line, &e) == nil {
			out = append(out, e)
		}
	}
	return out, sc.Err()
}