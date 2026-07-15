import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

interface Product {
  id: number;
  name: string;
  price: number;
}

interface PageResponse {
  products: Product[];
  nextPage?: number;
}

const fetchProducts = async ({ pageParam = 1 }: { pageParam?: number }): Promise<PageResponse> => {
  const response = await axios.get(`https://api.example.com/products?page=${pageParam}`);
  return response.data;
};

const InfiniteProductList: React.FC = () => {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, hasNextPage, fetchNextPage } = useInfiniteQuery(
    ['products'],
    fetchProducts,
    {
      getNextPageParam: (lastPage) => lastPage.nextPage,
    }
  );

  if (isLoading) return <div>Loading...</div>;
  if (isError) return <div>Error fetching products</div>;

  return (
    <ul>
      {data.pages.flatMap((page) => page.products).map((product) => (
        <li key={product.id}>{product.name} - ${product.price}</li>
      ))}
      {hasNextPage && (
        <button onClick={() => fetchNextPage()} disabled={isLoading}>
          Load More
        </button>
      )}
    </ul>
  );
};

export default InfiniteProductList;