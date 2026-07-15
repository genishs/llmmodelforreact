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

const fetchProducts = async ({ pageParam = 1 }) => {
  const response = await axios.get<PageResponse>(
    `https://api.example.com/products?page=${pageParam}`
  );
  return response.data;
};

const InfiniteScrollProductList = () => {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, hasNextPage, fetchNextPage } =
    useInfiniteQuery(['products'], fetchProducts, {
      getNextPageParam: (lastPage) => lastPage.nextPage,
    });

  if (isLoading) return <div>Loading...</div>;
  if (isError) return <div>Error fetching products</div>;

  return (
    <ul>
      {data.pages.map((page, index) =>
        page.products.map((product) => (
          <li key={`${index}-${product.id}`}>
            {product.name} - ${product.price}
          </li>
        ))
      )}
      {hasNextPage && !isLoading && (
        <button onClick={() => fetchNextPage()}>Load More</button>
      )}
    </ul>
  );
};

export default InfiniteScrollProductList;