import { useInfiniteQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Product { id: number; name: string; price: number; }

interface PageResponse {
  products: Product[];
  nextPage: number | null;
}

async function fetchProducts(pageParam = 1): Promise<PageResponse> {
  const res = await axios.get<{ data: PageResponse }>('/api/products', { params: { page: pageParam } });
  return res.data.data;
}

function ProductList() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    useInfiniteQuery<PageResponse>('products', fetchProducts, {
      getNextPageParam: (last) => last.nextPage,
    });

  if (isLoading) return <p>Loading...</p>;
  if (isError) return <p>Error fetching products</p>;

  return (
    <div>
      <ul>
        {data?.pages.flatMap((page) =>
          page.products.map((product) => (
            <li key={product.id}>{product.name} - ${product.price}</li>
          ))
        )}
      </ul>
      {hasNextPage && !isFetchingNextPage && (
        <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
          Load More
        </button>
      )}
      {isFetchingNextPage && <p>Loading more...</p>}
    </div>
  );
}

export default ProductList;