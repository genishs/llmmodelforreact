import { useState, useEffect } from 'react';

function useFetch<T>(url: string) {
  const [state, setState] = useState<{ status: 'loading' } | { status: 'error'; error: Error } | { status: 'success'; data: T }>({ status: 'loading' });
  useEffect(() => {
    fetch(url).then((res) => res.json()).then((data: T) => setState({ status: 'success', data })).catch((e) => setState({ status: 'error', error: e }));
  }, [url]);
  return state;
}

export default useFetch;