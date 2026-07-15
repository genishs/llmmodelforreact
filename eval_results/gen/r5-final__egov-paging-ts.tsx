import React from "react";

interface Pagination {
  currentPageNo?: number;
  totalRecordCount?: number;
  recordCountPerPage?: number;
  pageSize?: number;
}

interface Props {
  pagination?: Pagination;
  moveToPage: (pageNo: number) => void;
}

function EgovPaging({ pagination, moveToPage }: Props): JSX.Element {
  console.groupCollapsed("EgovPaging");
  console.log("EgovPaging [props] : ", { pagination, moveToPage });

  let paginationTag: JSX.Element[] = [];

  const currentPageNo = pagination?.currentPageNo ?? 1;
  const totalRecordCount = pagination?.totalRecordCount ?? 0;
  const recordCountPerPage = pagination?.recordCountPerPage ?? 10;
  const pageSize = pagination?.pageSize ?? 10;

  const totalPageCount = Math.ceil(totalRecordCount / recordCountPerPage);

  if (!pagination) {
    paginationTag = [<span key="none">-</span>];
  } else {
    const currentFirstPage =
      Math.floor((currentPageNo - 1) / pageSize) * pageSize + 1;
    let currentLastPage = currentFirstPage + pageSize - 1;
    currentLastPage = currentLastPage > totalPageCount ? totalPageCount : currentLastPage;

    for (let i = currentFirstPage; i <= currentLastPage; i++) {
      if (i === currentPageNo) {
        paginationTag.push(
          <div key={i}>
            <button className="num_on">
              <div className="num_on1"></div>
              {i}
            </button>
          </div>
        );
      } else {
        paginationTag.push(
          <div key={i}>
            <button
              className="num_off"
              onClick={() => moveToPage(i)}
            >
              {i}
            </button>
          </div>
        );
      }
    }
  }

  console.log("paginationTag", paginationTag);
  console.groupEnd("EgovPaging");

  return (
    <div className="num_wrap d_flex d_jcc aic">
      <button className="num_l img_all"
        onClick={() => {
          if (currentPageNo > 1) {
            moveToPage(currentPageNo - 1);
          }
        }}
        style={{ opacity: currentPageNo > 1 ? 1 : 0.5 }}
        tabIndex="0"
      >
      </button>

      {paginationTag}

      <button className="num_r img_all"
        onClick={() => {
          if (currentPageNo < totalPageCount) {
            moveToPage(currentPageNo + 1);
          }
        }}
        style={{ opacity: currentPageNo < totalPageCount ? 1 : 0.5 }}
        tabIndex="0"
      >
      </button>
    </div>
  );
}

export default EgovPaging;