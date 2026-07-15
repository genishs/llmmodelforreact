import { useState, useEffect } from 'react';

function useFetch<T>(url: string): {
  status: 'loading' | 'error' | 'success';
  error?: Error;
  data?: T;
} {
  const [state, setState] = useState<{
    status: 'loading' | 'error' | 'success';
    error?: Error;
    data?: T;
  }>({ status: 'loading' });

  useEffect(() => {
    let active = true;
    fetch(url)
      .then((r) => r.json())
      .then((d) => {
        if (!active) return;
        setState({ status: 'success', data: d as T });
      })
      .catch((e) => {
        if (!active) return;
        setState({ status: 'error', error: e });
      });
    return () => { active = false; };
  }, [url]);

  return state;
}

export default useFetch;