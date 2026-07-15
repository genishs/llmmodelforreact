import { useState, useEffect } from 'react';

interface Success<T> { status: 'success'; data: T; }
interface Loading { status: 'loading'; }
interface Error { status: 'error'; error: Error; }

function useFetch<T>(url: string): Success<T> | Loading | Error {
  const [state, setState] = useState<Success<T> | Loading>({ status: 'loading' });

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Network response was not ok');
        const data = (await res.json()) as T;
        setState({ status: 'success', data });
      } catch (e) {
        setState({ status: 'error', error: e instanceof Error ? e : new Error(String(e)) });
      }
    }
    fetchData();
  }, [url]);

  return state;
}

export default useFetch;