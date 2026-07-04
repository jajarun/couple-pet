// Generate a UUID that also works over plain HTTP on the LAN.
//
// `crypto.randomUUID()` only exists in a *secure context* (HTTPS or localhost),
// so on a phone hitting http://<mac-ip> it's undefined. `crypto.getRandomValues()`
// IS available in insecure contexts, so we hand-roll a v4 UUID from it, and fall
// back to Math.random() only if even that is missing.
export function randomId(): string {
  const c = globalThis.crypto
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()

  const bytes = new Uint8Array(16)
  if (c && typeof c.getRandomValues === 'function') {
    c.getRandomValues(bytes)
  } else {
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256)
  }
  // RFC 4122 v4: set version (4) and variant (10xx) bits
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80

  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'))
  return (
    hex.slice(0, 4).join('') +
    '-' +
    hex.slice(4, 6).join('') +
    '-' +
    hex.slice(6, 8).join('') +
    '-' +
    hex.slice(8, 10).join('') +
    '-' +
    hex.slice(10, 16).join('')
  )
}
