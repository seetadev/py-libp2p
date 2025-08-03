/**
 * @packageDocumentation
 *
 * This module exports various matchers that can be used to infer the type of a
 * passed multiaddr.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { DNS } from '@multiformats/multiaddr-matcher'
 *
 * const ma = multiaddr('/dnsaddr/example.org')
 *
 * DNS.matches(ma) // true - this is a multiaddr with a DNS address at the start
 * ```
 *
 * @example
 *
 * The default matching behaviour ignores any subsequent tuples in the multiaddr.
 * If you want stricter matching you can use `.exactMatch`:
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { DNS, Circuit } from '@multiformats/multiaddr-matcher'
 *
 * const ma = multiaddr('/dnsaddr/example.org/p2p/QmFoo/p2p-circuit/p2p/QmBar')
 *
 * DNS.exactMatch(ma) // false - this address has extra tuples after the DNS component
 * Circuit.matches(ma) // true
 * Circuit.exactMatch(ma) // true - the extra tuples are circuit relay related
 * ```
 */

import { CODE_P2P, CODE_DNS4, CODE_DNS6, CODE_DNSADDR, CODE_DNS, CODE_IP4, CODE_IP6, CODE_TCP, CODE_UDP, CODE_QUIC, CODE_QUIC_V1, CODE_WS, CODE_WSS, CODE_TLS, CODE_SNI, CODE_WEBRTC_DIRECT, CODE_CERTHASH, CODE_WEBTRANSPORT, CODE_P2P_CIRCUIT, CODE_WEBRTC, CODE_HTTP, CODE_UNIX, CODE_HTTPS, CODE_MEMORY, CODE_IP6ZONE, CODE_IPCIDR } from '@multiformats/multiaddr'
import { and, or, optional, fmt, code, value } from './utils.js'
import type { Multiaddr, Component } from '@multiformats/multiaddr'

/**
 * A matcher accepts multiaddr components and either fails to match and returns
 * false or returns a sublist of unmatched components
 */
export interface Matcher {
  match(parts: Component[]): Component[] | false
}

/**
 * A MultiaddrMatcher allows interpreting a multiaddr as a certain type of
 * multiaddr
 */
export interface MultiaddrMatcher {
  /**
   * The matchers that make up this MultiaddrMatcher - useful if you want to
   * make your own custom matchers
   */
  matchers: Matcher[]

  /**
   * Returns true if the passed multiaddr can be treated as this type of
   * multiaddr
   */
  matches(ma?: Multiaddr): boolean

  /**
   * Returns true if the passed multiaddr terminates as this type of
   * multiaddr
   */
  exactMatch(ma?: Multiaddr): boolean
}

/**
 * Matches PeerId addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { PEER_ID } from '@multiformats/multiaddr-matcher'
 *
 * PEER_ID.matches(multiaddr('/p2p/Qmfoo')) // true
 * PEER_ID.matches(multiaddr('/ipfs/Qmfoo')) // true
 * ```
 */
const _PEER_ID = value(CODE_P2P)

export const PEER_ID = fmt(_PEER_ID)

/**
 * DNS matchers
 */
const _DNS4 = value(CODE_DNS4)
const _DNS6 = value(CODE_DNS6)
const _DNSADDR = value(CODE_DNSADDR)
const _DNS = value(CODE_DNS)

/**
 * Matches dns4 addresses.
 *
 * Use {@link DNS DNS} instead to match any type of DNS address.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { DNS4 } from '@multiformats/multiaddr-matcher'
 *
 * DNS4.matches(multiaddr('/dns4/example.org')) // true
 * ```
 */
export const DNS4 = fmt(_DNS4, optional(value(CODE_P2P)))

/**
 * Matches dns6 addresses.
 *
 * Use {@link DNS DNS} instead to match any type of DNS address.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { DNS6 } from '@multiformats/multiaddr-matcher'
 *
 * DNS6.matches(multiaddr('/dns6/example.org')) // true
 * ```
 */
export const DNS6 = fmt(_DNS6, optional(value(CODE_P2P)))

/**
 * Matches dnsaddr addresses.
 *
 * Use {@link DNS DNS} instead to match any type of DNS address.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { DNSADDR } from '@multiformats/multiaddr-matcher'
 *
 * DNSADDR.matches(multiaddr('/dnsaddr/example.org')) // true
 * DNSADDR.matches(multiaddr('/dnsaddr/example.org/p2p/Qmfoo')) // true
 * ```
 */
export const DNSADDR = fmt(_DNSADDR, optional(value(CODE_P2P)))

/**
 * Matches any dns address.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { DNS } from '@multiformats/multiaddr-matcher'
 *
 * DNS.matches(multiaddr('/dnsaddr/example.org')) // true
 * DNS.matches(multiaddr('/dns4/example.org')) // true
 * DNS.matches(multiaddr('/dns6/example.org')) // true
 * DNS.matches(multiaddr('/dns6/example.org/p2p/Qmfoo')) // true
 * ```
 */
export const DNS = fmt(or(_DNS, _DNSADDR, _DNS4, _DNS6), optional(value(CODE_P2P)))

const _IP4 = and(
  value(CODE_IP4),
  optional(value(CODE_IPCIDR))
)
const _IP6 = and(
  optional(value(CODE_IP6ZONE)),
  value(CODE_IP6),
  optional(value(CODE_IPCIDR))
)
const _IP = or(_IP4, _IP6)

const _IP_OR_DOMAIN = or(_IP, _DNS, _DNS4, _DNS6, _DNSADDR)

/**
 * A matcher for addresses that start with IP or DNS tuples.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { IP_OR_DOMAIN } from '@multiformats/multiaddr-matcher'
 *
 * IP_OR_DOMAIN.matches(multiaddr('/ip4/123.123.123.123')) // true
 * IP_OR_DOMAIN.matches(multiaddr('/ip4/123.123.123.123/p2p/QmFoo')) // true
 * IP_OR_DOMAIN.matches(multiaddr('/dns/example.com/p2p/QmFoo')) // true
 * IP_OR_DOMAIN.matches(multiaddr('/p2p/QmFoo')) // false
 * ```
 */
export const IP_OR_DOMAIN = fmt(or(_IP, and(or(_DNS, _DNSADDR, _DNS4, _DNS6), optional(value(CODE_P2P)))))

/**
 * Matches ip4 addresses.
 *
 * Use {@link IP IP} instead to match any ip4/ip6 address.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { IP4 } from '@multiformats/multiaddr-matcher'
 *
 * const ma = multiaddr('/ip4/123.123.123.123')
 *
 * IP4.matches(ma) // true
 * ```
 */
export const IP4 = fmt(_IP4)

/**
 * Matches ip6 addresses.
 *
 * Use {@link IP IP} instead to match any ip4/ip6 address.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { IP6 } from '@multiformats/multiaddr-matcher'
 *
 * const ma = multiaddr('/ip6/fe80::1cc1:a3b8:322f:cf22')
 *
 * IP6.matches(ma) // true
 * ```
 */
export const IP6 = fmt(_IP6)

/**
 * Matches ip4 or ip6 addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { IP } from '@multiformats/multiaddr-matcher'
 *
 * IP.matches(multiaddr('/ip4/123.123.123.123')) // true
 * IP.matches(multiaddr('/ip6/fe80::1cc1:a3b8:322f:cf22')) // true
 * ```
 */
export const IP = fmt(_IP)

const _TCP = and(_IP_OR_DOMAIN, value(CODE_TCP))
const _UDP = and(_IP_OR_DOMAIN, value(CODE_UDP))

/**
 * Matches TCP addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { TCP } from '@multiformats/multiaddr-matcher'
 *
 * TCP.matches(multiaddr('/ip4/123.123.123.123/tcp/1234')) // true
 * ```
 */
export const TCP = fmt(and(_TCP, optional(value(CODE_P2P))))

/**
 * Matches UDP addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { UDP } from '@multiformats/multiaddr-matcher'
 *
 * UDP.matches(multiaddr('/ip4/123.123.123.123/udp/1234')) // true
 * ```
 */
export const UDP = fmt(_UDP)

const _QUIC = and(_UDP, code(CODE_QUIC), optional(value(CODE_P2P)))
const _QUIC_V1 = and(_UDP, code(CODE_QUIC_V1), optional(value(CODE_P2P)))

const QUIC_V0_OR_V1 = or(_QUIC, _QUIC_V1)

/**
 * Matches QUIC addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { QUIC } from '@multiformats/multiaddr-matcher'
 *
 * QUIC.matches(multiaddr('/ip4/123.123.123.123/udp/1234/quic')) // true
 * ```
 */
export const QUIC = fmt(_QUIC)

/**
 * Matches QUICv1 addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { QUIC_V1 } from '@multiformats/multiaddr-matcher'
 *
 * QUIC_V1.matches(multiaddr('/ip4/123.123.123.123/udp/1234/quic-v1')) // true
 * ```
 */
export const QUIC_V1 = fmt(_QUIC_V1)

const _WEB = or(
  _IP_OR_DOMAIN,
  _TCP,
  _UDP,
  _QUIC,
  _QUIC_V1
)

const _WebSockets = or(
  and(_WEB, code(CODE_WS), optional(value(CODE_P2P)))
)

/**
 * Matches WebSocket addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { WebSockets } from '@multiformats/multiaddr-matcher'
 *
 * WebSockets.matches(multiaddr('/ip4/123.123.123.123/tcp/1234/ws')) // true
 * ```
 */
export const WebSockets = fmt(_WebSockets)

const _WebSocketsSecure = or(
  and(_WEB, code(CODE_WSS), optional(value(CODE_P2P))),
  and(_WEB, code(CODE_TLS), optional(value(CODE_SNI)), code(CODE_WS), optional(value(CODE_P2P)))
)

/**
 * Matches secure WebSocket addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { WebSocketsSecure } from '@multiformats/multiaddr-matcher'
 *
 * WebSocketsSecure.matches(multiaddr('/ip4/123.123.123.123/tcp/1234/wss')) // true
 * ```
 */
export const WebSocketsSecure = fmt(_WebSocketsSecure)

const _WebRTCDirect = and(_UDP, code(CODE_WEBRTC_DIRECT), optional(value(CODE_CERTHASH)), optional(value(CODE_CERTHASH)), optional(value(CODE_P2P)))

/**
 * Matches WebRTC-direct addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { WebRTCDirect } from '@multiformats/multiaddr-matcher'
 *
 * WebRTCDirect.matches(multiaddr('/ip4/123.123.123.123/tcp/1234/p2p/QmFoo/webrtc-direct/certhash/u....')) // true
 * ```
 */
export const WebRTCDirect = fmt(_WebRTCDirect)

const _WebTransport = and(_QUIC_V1, code(CODE_WEBTRANSPORT), optional(value(CODE_CERTHASH)), optional(value(CODE_CERTHASH)), optional(value(CODE_P2P)))

/**
 * Matches WebTransport addresses.
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { WebRTCDirect } from '@multiformats/multiaddr-matcher'
 *
 * WebRTCDirect.matches(multiaddr('/ip4/123.123.123.123/udp/1234/quic-v1/webtransport/certhash/u..../certhash/u..../p2p/QmFoo')) // true
 * ```
 */
export const WebTransport = fmt(_WebTransport)

const _P2P = or(
  _WebSockets,
  _WebSocketsSecure,
  and(_TCP, optional(value(CODE_P2P))),
  and(QUIC_V0_OR_V1, optional(value(CODE_P2P))),
  and(_IP_OR_DOMAIN, optional(value(CODE_P2P))),
  _WebRTCDirect,
  _WebTransport,
  value(CODE_P2P)
)

/**
 * Matches peer addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { P2P } from '@multiformats/multiaddr-matcher'
 *
 * P2P.matches(multiaddr('/ip4/123.123.123.123/tcp/1234/p2p/QmFoo')) // true
 * ```
 */
export const P2P = fmt(_P2P)

const _Circuit = and(_P2P, code(CODE_P2P_CIRCUIT), value(CODE_P2P))

/**
 * Matches circuit relay addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { Circuit } from '@multiformats/multiaddr-matcher'
 *
 * Circuit.matches(multiaddr('/ip4/123.123.123.123/tcp/1234/p2p/QmRelay/p2p-circuit/p2p/QmTarget')) // true
 * ```
 */
export const Circuit = fmt(_Circuit)

const _WebRTC = or(
  and(_P2P, code(CODE_P2P_CIRCUIT), code(CODE_WEBRTC), optional(value(CODE_P2P))),
  and(_P2P, code(CODE_WEBRTC), optional(value(CODE_P2P))),
  and(code(CODE_WEBRTC), optional(value(CODE_P2P)))
)

/**
 * Matches WebRTC addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { WebRTC } from '@multiformats/multiaddr-matcher'
 *
 * WebRTC.matches(multiaddr('/ip4/123.123.123.123/tcp/1234/p2p/QmRelay/p2p-circuit/webrtc/p2p/QmTarget')) // true
 * ```
 */
export const WebRTC = fmt(_WebRTC)

const _HTTP = or(
  and(_IP_OR_DOMAIN, value(CODE_TCP), code(CODE_HTTP), optional(value(CODE_P2P))),
  and(_IP_OR_DOMAIN, code(CODE_HTTP), optional(value(CODE_P2P)))
)

/**
 * Matches HTTP addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { HTTP } from '@multiformats/multiaddr-matcher'
 *
 * HTTP.matches(multiaddr('/dns/example.org/http')) // true
 * ```
 */
export const HTTP = fmt(_HTTP)

const _HTTPS = and(_IP_OR_DOMAIN, or(
  and(value(CODE_TCP, '443'), code(CODE_HTTP)),
  and(value(CODE_TCP), code(CODE_HTTPS)),
  and(value(CODE_TCP), code(CODE_TLS), code(CODE_HTTP)),
  and(code(CODE_TLS), code(CODE_HTTP)),
  code(CODE_TLS),
  code(CODE_HTTPS)
),
optional(value(CODE_P2P))
)

/**
 * Matches HTTPS addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { HTTP } from '@multiformats/multiaddr-matcher'
 *
 * HTTP.matches(multiaddr('/dns/example.org/tls/http')) // true
 * ```
 */
export const HTTPS = fmt(_HTTPS)

const _Memory = or(
  and(value(CODE_MEMORY), optional(value(CODE_P2P)))
)

/**
 * Matches Memory addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { Memory } from '@multiformats/multiaddr-matcher'
 *
 * Memory.matches(multiaddr('/memory/0xDEADBEEF')) // true
 * ```
 */
export const Memory = fmt(_Memory)

const _Unix = or(
  and(value(CODE_UNIX), optional(value(CODE_P2P)))
)

/**
 * Matches Unix addresses
 *
 * @example
 *
 * ```ts
 * import { multiaddr } from '@multiformats/multiaddr'
 * import { Unix } from '@multiformats/multiaddr-matcher'
 *
 * Unix.matches(multiaddr('/unix/%2Fpath%2Fto%2Funix.socket')) // true
 * ```
 */
export const Unix = fmt(_Unix)
