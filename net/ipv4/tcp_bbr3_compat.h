/* SPDX-License-Identifier: (BSD-3-Clause OR GPL-2.0) */
/*
 * bbr_compat.h - compatibility shim for building BBRv3 (tcp_bbr3.c) on
 * kernels that lack the BBRv3-era TCP stack extensions (i.e. any mainline
 * kernel; the extensions currently only exist in Google's bbr tree).
 *
 * Deliberately NO LINUX_VERSION_CODE branching: all feature knowledge comes
 * from the baked probe-result block below (in-tree adaptation: the
 * gen_kconfig.py build-time generator is not used).
 * The generator test-compiles one small module per probe in kapi_checklist
 * against the *actual* target kernel tree and emits HAVE_* macros. This
 * survives distro/vendor kernels that backport arbitrary subsets of newer
 * APIs, where version-based checks would guess wrong.
 */
#pragma once

#include <linux/kernel.h>
#include <linux/bitops.h>
#include <linux/random.h>
#include <net/tcp.h>
#include <net/inet_connection_sock.h>

/* Probe results baked for this tree (android15-6.6, 6.6.142),
 * determined by direct inspection of the target headers - equivalent
 * to running gen_kconfig.py from hrimfaxi/tcp_bbr_modules against
 * this tree. Re-probe if the kernel base changes.
 */
#define HAVE_TCP_ECN_OK 1
#define HAVE_TCP_CONG_NEEDS_ECN 1
#define HAVE_CA_EVENT_ECN_IS_CE 1
#define HAVE_RATE_SAMPLE_LOSSES 1
#define HAVE_RATE_SAMPLE_PRIOR_IN_FLIGHT 1
#define HAVE_RATE_SAMPLE_DELIVERED_CE 1
#define HAVE_TCP_SOCK_DELIVERED_CE 1
#define HAVE_TCP_SOCK_IS_SACK_RENEG 1
#define HAVE_TCP_SOCK_LOST 1
#define HAVE_TCP_SOCK_LOST_OUT 1
#define HAVE_TCP_SOCK_PRIOR_CWND 1
#define HAVE_TCP_SOCK_TCP_CLOCK_CACHE 1
#define HAVE_TCP_SOCK_ECN_FLAGS 1
#define HAVE_TCP_SOCK_SND_CWND 1
#define HAVE_SKB_CB_TX_DELIVERED_MSTAMP 1
#define HAVE_SKB_CB_TX_IS_APP_LIMITED 1
#define HAVE_TCP_SND_CWND 1
#define HAVE_TCP_SND_CWND_SET 1
#define HAVE_TCP_STAMP_US_DELTA 1
#define HAVE_TCP_MIN_RTT 1
#define HAVE___TCP_SEND_ACK 1
#define HAVE_GET_RANDOM_U32_BELOW 1
#define HAVE_TCP_PLB_STATE 1
#define HAVE_TCP_PLB_SCALE 1
#define HAVE_TCP_PLB_UPDATE_STATE 1
#define HAVE_TCP_PLB_CHECK_REHASH 1
#define HAVE_TCP_PLB_UPDATE_STATE_UPON_RTO 1
#define HAVE_SYSCTL_TCP_PLB_ENABLED 1
#define HAVE_ICSK_CA_PRIV 1
/* Deliberately NOT defined for this tree (absent from 6.6 headers):
 * TCP_CONGESTION_OPS_CONG_CONTROL_HAS_4_ARGS (6.6 cong_control is
 * 2-arg), TCP_CONGESTION_OPS_HAS_TSO_SEGS,
 * TCP_CONGESTION_OPS_HAS_SKB_MARKED_LOST, HAVE_TCP_ECN_LOW,
 * HAVE_TCP_ECN_ECT_PERMANENT, HAVE_TCP_CONG_WANTS_CE_EVENTS,
 * HAVE_CA_EVENT_TLP_RECOVERY, HAVE_RATE_SAMPLE_LOST,
 * HAVE_RATE_SAMPLE_TX_IN_FLIGHT, HAVE_RATE_SAMPLE_IS_ACKING_TLP_RETRANS_SEQ,
 * HAVE_RATE_SAMPLE_IS_ECE, HAVE_TCP_SOCK_FAST_ACK_MODE,
 * HAVE_TCP_SOCK_TLP_ORIG_DATA_APP_LIMITED, HAVE_SKB_CB_TX_IN_FLIGHT,
 * HAVE_SKB_CB_TX_LOST, HAVE_TCP_BBR_PHASE, HAVE_TCP_BBR_INFO_V2
 */

struct bbr;	/* defined in tcp_bbr3.c */

/* --------------------------------------------------------------------------
 * struct bbr allocation
 *
 * struct bbr for BBRv3 is ~200 bytes; icsk_ca_priv is 104 bytes on every
 * mainline kernel (<= 6.6). We therefore keep a pointer in icsk_ca_priv and
 * kzalloc() the real state block in bbr_init(); bbr_release() frees it.
 * ------------------------------------------------------------------------ */
static inline struct bbr **bbr_ca_slot(struct sock *sk)
{
	return (struct bbr **)inet_csk_ca(sk);
}

static inline struct bbr *bbr_ca(const struct sock *sk)
{
	return *(struct bbr **)inet_csk_ca(sk);
}

/* --------------------------------------------------------------------------
 * snd_cwnd accessors (added in ~5.15; older kernels access tp->snd_cwnd)
 * ------------------------------------------------------------------------ */
#ifndef HAVE_TCP_SND_CWND
static inline u32 tcp_snd_cwnd(const struct tcp_sock *tp)
{
	return tp->snd_cwnd;
}
#endif

#ifndef HAVE_TCP_SND_CWND_SET
static inline void tcp_snd_cwnd_set(struct tcp_sock *tp, u32 val)
{
	tp->snd_cwnd = val;
}
#endif

/* --------------------------------------------------------------------------
 * get_random_u32_below() (6.2+, backported to some 6.1 stables)
 * ------------------------------------------------------------------------ */
#ifndef HAVE_GET_RANDOM_U32_BELOW
#ifdef HAVE_PRANDOM_U32_MAX
#include <linux/prandom.h>
#define get_random_u32_below(x) prandom_u32_max(x)
#else
#error "need either get_random_u32_below() or prandom_u32_max()"
#endif
#endif

/* --------------------------------------------------------------------------
 * misc macros that may be absent (plain #ifndef works: they are macros)
 * ------------------------------------------------------------------------ */
#ifndef __bpf_kfunc
#define __bpf_kfunc
#endif

#ifndef GSO_LEGACY_MAX_SIZE
#define GSO_LEGACY_MAX_SIZE 65536
#endif

#ifndef BITS_PER_TYPE
#define BITS_PER_TYPE(type) (sizeof(type) * BITS_PER_BYTE)
#endif

#ifndef HAVE_TCP_STAMP_US_DELTA
static inline u32 tcp_stamp_us_delta(u64 t1, u64 t0)
{
	return max_t(s64, t1 - t0, 0);
}
#endif

/* --------------------------------------------------------------------------
 * ECN flags in tp->ecn_flags
 *
 * TCP_ECN_OK: "connection may use ECN". Present on every kernel we care
 * about; the fallback value matches the classic mainline bit.
 *
 * TCP_ECN_LOW: "shallow-threshold (L4S-like) ECN on this route". Google-tree
 * only. On mainline we emulate it with the bbr_ecn_low module parameter;
 * define it as 0 so bit-tests compile away.
 * ------------------------------------------------------------------------ */
#ifndef HAVE_TCP_ECN_OK
#define TCP_ECN_OK		1
#endif

#ifndef HAVE_TCP_ECN_LOW
#define TCP_ECN_LOW		0
#endif

/* --------------------------------------------------------------------------
 * enum tcp_ca_event: CA_EVENT_TLP_RECOVERY is Google-tree only. The core
 * stack on mainline never generates it, so the exact value only needs to
 * not collide with existing events (mainline ends at CA_EVENT_ECN_IS_CE=5).
 * ------------------------------------------------------------------------ */
#ifndef HAVE_CA_EVENT_TLP_RECOVERY
#define CA_EVENT_TLP_RECOVERY	8
#endif

/* --------------------------------------------------------------------------
 * struct rate_sample field accessors.
 *
 * Mainline has: delivered, losses, acked_sacked, prior_in_flight, rtt_us,
 *               interval_us, is_app_limited, is_ack_delayed, ...
 *               (+ delivered_ce, prior_delivered_ce since ~6.1)
 * Google tree adds: lost, tx_in_flight, is_acking_tlp_retrans_seq, is_ece.
 * ------------------------------------------------------------------------ */
#if defined(HAVE_RATE_SAMPLE_LOST)
#define bbr_rs_lost(rs)			((rs)->lost)
#elif defined(HAVE_RATE_SAMPLE_LOSSES)
#define bbr_rs_lost(rs)			((rs)->losses)
#else
#error "struct rate_sample has neither 'lost' nor 'losses'"
#endif

/* tx_in_flight = packets in flight when the (S)ACKed skb was sent.
 * Best mainline approximation: inflight right before this ACK was processed.
 */
#if defined(HAVE_RATE_SAMPLE_TX_IN_FLIGHT)
#define bbr_rs_tx_in_flight(rs)		((rs)->tx_in_flight)
#elif defined(HAVE_RATE_SAMPLE_PRIOR_IN_FLIGHT)
#define bbr_rs_tx_in_flight(rs)		((rs)->prior_in_flight)
#else
#error "struct rate_sample has neither 'tx_in_flight' nor 'prior_in_flight'"
#endif

#ifdef HAVE_RATE_SAMPLE_IS_ACKING_TLP_RETRANS_SEQ
#define bbr_rs_is_acking_tlp(rs)	((rs)->is_acking_tlp_retrans_seq)
#else
#define bbr_rs_is_acking_tlp(rs)	(false)
#endif

#ifdef HAVE_RATE_SAMPLE_IS_ECE
#define bbr_rs_is_ece(rs)		((rs)->is_ece)
#elif defined(HAVE_RATE_SAMPLE_DELIVERED_CE)
#define bbr_rs_is_ece(rs)		((rs)->delivered_ce > 0)
#else
#define bbr_rs_is_ece(rs)		(false)
#endif

#ifdef HAVE_RATE_SAMPLE_DELIVERED_CE
#define bbr_rs_delivered_ce(rs)		((rs)->delivered_ce)
#else
#define bbr_rs_delivered_ce(rs)		(0)
#endif

/* --------------------------------------------------------------------------
 * struct tcp_sock field accessors
 * ------------------------------------------------------------------------ */
#ifdef HAVE_TCP_SOCK_DELIVERED_CE
#define bbr_tp_delivered_ce(tp)		((tp)->delivered_ce)
#else
#define bbr_tp_delivered_ce(tp)		(0)
#endif

#ifdef HAVE_TCP_SOCK_TCP_CLOCK_CACHE
#define bbr_tcp_clock_ns(tp)		((tp)->tcp_clock_cache)
#else
#define bbr_tcp_clock_ns(tp)		((tp)->tcp_mstamp * NSEC_PER_USEC)
#endif

#ifdef HAVE_TCP_SOCK_IS_SACK_RENEG
#define bbr_is_sack_reneg(tp)		((tp)->is_sack_reneg)
#else
#define bbr_is_sack_reneg(tp)		(0)
#endif

#ifdef HAVE_TCP_SOCK_LOST
#define bbr_tp_lost(tp)			((tp)->lost)
#elif defined(HAVE_TCP_SOCK_LOST_OUT)
#define bbr_tp_lost(tp)			((tp)->lost_out)
#else
#define bbr_tp_lost(tp)			(0)
#endif

#ifdef HAVE_TCP_SOCK_TLP_ORIG_DATA_APP_LIMITED
#define bbr_tlp_orig_data_app_limited(tp) ((tp)->tlp_orig_data_app_limited)
#else
#define bbr_tlp_orig_data_app_limited(tp) (false)
#endif

#ifdef HAVE_TCP_SOCK_PRIOR_CWND
#define bbr_init_prior_cwnd(tp)		((tp)->prior_cwnd)
#else
#define bbr_init_prior_cwnd(tp)		tcp_snd_cwnd(tp)
#endif

/* --------------------------------------------------------------------------
 * PLB (Protective Load Balancing). Mainline has it since 6.2; BBRv3 code
 * calls it unconditionally, so provide no-op stubs when missing.
 * ------------------------------------------------------------------------ */
#ifndef HAVE_TCP_PLB_STATE
struct tcp_plb_state {
	u32	pause_until;	/* jiffies32 when PLB can resume rerouting */
};
#endif

#ifndef HAVE_TCP_PLB_UPDATE_STATE
static inline void tcp_plb_update_state(const struct sock *sk,
					struct tcp_plb_state *plb,
					const int cong_ratio)
{
}
#endif

#ifndef HAVE_TCP_PLB_CHECK_REHASH
static inline void tcp_plb_check_rehash(struct sock *sk,
					struct tcp_plb_state *plb)
{
}
#endif

#ifndef HAVE_TCP_PLB_UPDATE_STATE_UPON_RTO
static inline void tcp_plb_update_state_upon_rto(struct sock *sk,
						 struct tcp_plb_state *plb)
{
}
#endif

#ifdef HAVE_SYSCTL_TCP_PLB_ENABLED
#define bbr_sysctl_tcp_plb_enabled(net) \
	READ_ONCE((net)->ipv4.sysctl_tcp_plb_enabled)
#else
#define bbr_sysctl_tcp_plb_enabled(net) (false)
#endif

/* --------------------------------------------------------------------------
 * bbr_skb_tx_in_flight_is_suspicious(): sanity check for per-skb tx_in_flight
 * on the (Google-tree only) skb_marked_lost path. Always use our own copy
 * under our own name: the Google-tree helper's exact signature differs from
 * this call-site contract, and defining a same-named static inline would
 * collide with the native declaration whenever the probe arg-count guess
 * is wrong.
 * ------------------------------------------------------------------------ */
static inline bool bbr_skb_tx_in_flight_is_suspicious(u32 pcount,
						     u32 sacked_out,
						     u32 tx_in_flight)
{
	return tx_in_flight > pcount + sacked_out;
}

/* --------------------------------------------------------------------------
 * enum tcp_bbr_phase (UAPI for INET_DIAG_BBRINFO; added together with the
 * extended struct tcp_bbr_info). Needed to fill bbr_phase on kernels whose
 * UAPI lacks it.
 * ------------------------------------------------------------------------ */
#ifndef HAVE_TCP_BBR_PHASE
enum tcp_bbr_phase {
	BBR_PHASE_STARTUP,
	BBR_PHASE_DRAIN,
	BBR_PHASE_PROBE_BW_UP,
	BBR_PHASE_PROBE_BW_DOWN,
	BBR_PHASE_PROBE_BW_CRUISE,
	BBR_PHASE_PROBE_BW_REFILL,
	BBR_PHASE_PROBE_RTT,
	BBR_PHASE_INVALID,
};
#endif

/* --------------------------------------------------------------------------
 * DCTCP-style ECE ACK update (precise CE echoing). Mainline keeps the real
 * helper in the *private* net/ipv4/tcp_dctcp.h, unreachable for out-of-tree
 * modules; copy the logic here. __tcp_send_ack() is EXPORT_SYMBOL_GPL on all
 * supported kernels; without it, degrade to just flagging ACK_NOW/CWR.
 * ------------------------------------------------------------------------ */
static inline void bbr_ece_ack_cwr(struct sock *sk, u32 ce_state)
{
	struct tcp_sock *tp = tcp_sk(sk);

	if (ce_state == 1)
		tp->ecn_flags |= TCP_ECN_DEMAND_CWR;
	else
		tp->ecn_flags &= ~TCP_ECN_DEMAND_CWR;
}

static inline void bbr_ece_ack_update(struct sock *sk, enum tcp_ca_event evt,
				      u32 *prior_rcv_nxt, u32 *ce_state)
{
	u32 new_ce_state = (evt == CA_EVENT_ECN_IS_CE) ? 1 : 0;

	if (*ce_state != new_ce_state) {
		/* CE state has changed, force an immediate ACK to reflect
		 * the new CE state. If an ACK was delayed, send that first
		 * to reflect the prior CE state.
		 */
#ifdef HAVE___TCP_SEND_ACK
		if (inet_csk(sk)->icsk_ack.pending & ICSK_ACK_TIMER) {
			bbr_ece_ack_cwr(sk, *ce_state);
			__tcp_send_ack(sk, *prior_rcv_nxt, 0);
		}
#endif
		inet_csk(sk)->icsk_ack.pending |= ICSK_ACK_NOW;
	}
	*prior_rcv_nxt = tcp_sk(sk)->rcv_nxt;
	*ce_state = new_ce_state;
	bbr_ece_ack_cwr(sk, new_ce_state);
}
