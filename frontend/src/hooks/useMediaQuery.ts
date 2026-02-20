import { useEffect, useState } from 'react';

const FALLBACK_MATCHES = false;

/**
 * React hook for tracking CSS media query matches.
 */
export const useMediaQuery = (query: string): boolean => {
  const getMatches = (): boolean => {
    if (typeof window === 'undefined') {
      return FALLBACK_MATCHES;
    }
    return window.matchMedia(query).matches;
  };

  const [matches, setMatches] = useState<boolean>(getMatches);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const mediaQueryList = window.matchMedia(query);
    const listener = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    setMatches(mediaQueryList.matches);
    mediaQueryList.addEventListener('change', listener);

    return () => {
      mediaQueryList.removeEventListener('change', listener);
    };
  }, [query]);

  return matches;
};

