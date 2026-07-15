import { useState, useEffect } from 'react';

function useFetch<T>(url: string) {
  const [state, setState] = useState<{ status: 'loading' } | { status: 'error'; error: Error } | { status: 'success'; data: T }>({ status: 'loading' });
  useEffect(() => {
    fetch(url).then((res) => res.json()).then((data) => setState({ status: 'success', data })).catch((err) => setState({ status: 'error', error: err }));
  }, [url]);
  return state;
}

export default useFetch;