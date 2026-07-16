import { useState, useEffect } from 'react';

type FetchStatus = 'loading' | 'error' | 'success';
type FetchData<T> = { status: FetchStatus; error?: Error; data?: T };

function useFetch<T>(url: string): FetchData<T> {
  const [state, setState] = useState<FetchData<T>>({ status: 'loading' });

  useEffect(() => {
    let isMounted = true;

    async function fetchData() {
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Network response was not ok');
        const data = (await response.json()) as T;
        if (isMounted) setState({ status: 'success', data });
      } catch (error) {
        if (isMounted) setState({ status: 'error', error });
      }
    }

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [url]);

  return state;
}

export default useFetch;