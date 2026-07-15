import { useState, useEffect } from 'react';

interface FetchState<T> {
  status: 'loading';
} | {
  status: 'error';
  error: Error;
} | {
  status: 'success';
  data: T;
};

function useFetch<T>(url: string): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({ status: 'loading' });

  useEffect(() => {
    fetch(url)
      .then((res) => res.json() as Promise<T>)
      .then((data) => setState({ status: 'success', data }))
      .catch((err) => setState({ status: 'error', error: err }));
  }, [url]);

  return state;
}

export default useFetch;