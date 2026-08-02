// Command veda-relay is the VEDA hub: a TLS1.3 WebSocket relay with device
// registry, authentication, audit logging and the control/consent engine.
//
// Usage:
//
//	veda-relay --listen :8080 [--ui ./dist] [--tls-cert c.pem --tls-key k.pem] [-a ./audit]
package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/audit"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/auth"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/hub"
	"github.com/purveshnileshbhadale/vayu/veda/relay/internal/server"
)

func main() {
	listen := flag.String("listen", ":8080", "listen address")
	tlsCert := flag.String("tls-cert", "", "TLS cert path (enables TLS 1.3)")
	tlsKey := flag.String("tls-key", "", "TLS key path")
	ui := flag.String("ui", "", "dashboard static dir (empty = bundled JS app served by relay)")
	auditPath := flag.String("audit", "veda-audit", "audit log directory")
	dashToken := flag.String("dash-token", "", "bearer token required for /audit")
	claimToken := flag.String("token", "", "shared claim/pair token devices must present (issued immediately)")
	flag.Parse()

	sess := auth.New()
	if *claimToken != "" {
		sess.IssueToken(*claimToken)
		log.Printf("claim token issued (sha256 %s)", auth.Hash(*claimToken))
	}
	logger, err := audit.New(auditDir(*auditPath))
	if err != nil {
		log.Fatalf("audit: %v", err)
	}
	defer logger.Close()

	h := hub.New(sess)
	h.SetLogger(logger)

	srv := server.New(server.Opts{
		Listen:         *listen,
		TLSCert:        *tlsCert,
		TLSKey:         *tlsKey,
		StaticDir:      *ui,
		DashboardToken: *dashToken,
	}, h, logger)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := srv.Run(ctx); err != nil && ctx.Err() == nil {
		log.Fatalf("server: %v", err)
	}
	log.Println("VEDA relay stopped")
}

func auditDir(p string) string {
	if p == "" {
		return "./vauda-audit"
	}
	return p
}