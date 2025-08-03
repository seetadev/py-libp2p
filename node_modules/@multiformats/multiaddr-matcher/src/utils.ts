import type { Matcher, MultiaddrMatcher } from './index.js'
import type { Multiaddr, Component } from '@multiformats/multiaddr'

/**
 * Matches a multiaddr component with the specified code but no value
 */
export const code = (code: number): Matcher => {
  return {
    match: (vals) => {
      const component = vals[0]

      if (component == null) {
        return false
      }

      if (component.code !== code) {
        return false
      }

      if (component.value != null) {
        return false
      }

      return vals.slice(1)
    }
  }
}

/**
 * Matches a multiaddr component with the specified code and value. If the value
 * is omitted any non-undefined value is matched.
 */
export const value = (code: number, value?: string): Matcher => {
  return {
    match: (vals) => {
      const component = vals[0]

      if (component?.code !== code) {
        return false
      }

      if (component.value == null) {
        return false
      }

      if (value != null && component.value !== value) {
        return false
      }

      return vals.slice(1)
    }
  }
}

/**
 * An optional matcher
 */
export const optional = (matcher: Matcher): Matcher => {
  return {
    match: (vals) => {
      const result = matcher.match(vals)

      if (result === false) {
        return vals
      }

      return result
    }
  }
}

/**
 * Matches any one of the passed matches
 */
export const or = (...matchers: Matcher[]): Matcher => {
  return {
    match: (vals) => {
      let matches: Component[] | undefined

      for (const matcher of matchers) {
        const result = matcher.match(vals)

        // no match
        if (result === false) {
          continue
        }

        // choose greediest matcher
        if (matches == null || result.length < matches.length) {
          matches = result
        }
      }

      if (matches == null) {
        return false
      }

      return matches
    }
  }
}

/**
 * Matches all of the passed matchers
 */
export const and = (...matchers: Matcher[]): Matcher => {
  return {
    match: (vals) => {
      for (const matcher of matchers) {
        // pass what's left of the array
        const result = matcher.match(vals)

        // no match
        if (result === false) {
          return false
        }

        vals = result
      }

      return vals
    }
  }
}

/**
 * Create a multiaddr matcher from the passed component matchers
 */
export function fmt (...matchers: Matcher[]): MultiaddrMatcher {
  function match (ma?: Multiaddr): Component[] | false {
    if (ma == null) {
      return false
    }

    let parts = ma.getComponents()

    for (const matcher of matchers) {
      const result = matcher.match(parts)

      if (result === false) {
        return false
      }

      parts = result
    }

    return parts
  }

  function matches (ma?: Multiaddr): boolean {
    const result = match(ma)

    return result !== false
  }

  function exactMatch (ma?: Multiaddr): boolean {
    const result = match(ma)

    if (result === false) {
      return false
    }

    return result.length === 0
  }

  return {
    matchers,
    matches,
    exactMatch
  }
}
