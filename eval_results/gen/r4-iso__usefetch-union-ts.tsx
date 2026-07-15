import { useState, useEffect } from 'react';

function useFetch<T>(url: string) {
  const [state, setState] = useState<{ status: 'loading' } | { status: 'error'; error: Error } | { status: 'success'; data: T }>({ status: 'loading' });

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Network response was not ok');
        const json = (await res.json()) as T;
        setState({ status: 'success', data: json });
      } catch (e) {
        setState({ status: 'error', error: e instanceof Error ? e : new Error(String(e)) });
      }
    }

    fetchData();
  }, [url]);

  return state;
}

export default useFetch;