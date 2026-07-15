import { useState, useEffect } from 'react';

type State<T> = { status: 'loading' } | { status: 'error'; error: Error } | { status: 'success'; data: T };

function useFetch<T>(url: string): State<T> {
  const [state, setState] = useState<State<T>>({ status: 'loading' });

  useEffect(() => {
    fetch(url)
      .then((r) => r.json())
      .then((data) => setState({ status: 'success', data }))
      .catch((e) => setState({ status: 'error', error: e }));
  }, [url]);

  return state;
}

export default useFetch;