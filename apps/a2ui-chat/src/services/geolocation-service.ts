/**
 * Geolocation Service
 *
 * Requests the user's location via the browser Geolocation API.
 * Caches the result so the prompt is only shown once per session.
 * If denied or unavailable, returns null — the AI can still respond
 * with general info and prompt the user to share their location.
 */

export interface UserLocation {
  lat: number;
  lng: number;
  /** Reverse-geocoded city/region (populated after lookup). */
  label?: string;
}

let cached: UserLocation | null = null;
let prompted = false;

/**
 * Get the user's location. Returns cached result on subsequent calls.
 * Returns null if denied, unavailable, or timed out (5 s).
 */
export async function getUserLocation(): Promise<UserLocation | null> {
  if (cached) return cached;
  if (prompted) return null; // Already asked, don't re-prompt

  if (!navigator.geolocation) return null;

  prompted = true;

  try {
    const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 5000,
        maximumAge: 300_000, // Cache for 5 min
      });
    });

    cached = { lat: pos.coords.latitude, lng: pos.coords.longitude };

    // Best-effort reverse geocode via free Nominatim API
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?lat=${cached.lat}&lon=${cached.lng}&format=json&zoom=10`,
        { signal: AbortSignal.timeout(3000) },
      );
      if (res.ok) {
        const data = await res.json();
        const parts: string[] = [];
        if (data.address?.city || data.address?.town || data.address?.village) {
          parts.push(data.address.city || data.address.town || data.address.village);
        }
        if (data.address?.state) parts.push(data.address.state);
        if (data.address?.country_code) parts.push(data.address.country_code.toUpperCase());
        if (parts.length) cached.label = parts.join(', ');
      }
    } catch {
      // Reverse geocode failed — lat/lng alone is still useful
    }

    return cached;
  } catch {
    // Denied or timed out
    return null;
  }
}

/** True if location is already cached (i.e. won't block). */
export function isLocationCached(): boolean {
  return cached !== null;
}

/** Clear cached location (e.g. on logout). */
export function clearLocationCache() {
  cached = null;
  prompted = false;
}
