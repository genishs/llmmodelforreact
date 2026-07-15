import React from 'react';

interface Props {
  pagination?: {
    currentPageNo?: number;
    totalRecordCount?: number;
    recordCountPerPage?: number;
    pageSize?: number;
  };
  moveToPage: (pageNo: number) => void;
}

const EgovPaging: React.FC<Props> = ({ pagination, moveToPage }) => {
  console.groupCollapsed("EgovPaging");
  console.log("EgovPaging [props] : ", { pagination, moveToPage });

  let paginationTag: JSX.Element[] = [];

  // 1. 핵심 변수를 초기값으로 정의하거나 props에서 바로 추출
  // **주의: 초기화된 변수(let currentPageNo = 1;)를 사용하지 않고,
  //         아래 if 블록 내에서만 유효한 값을 계산합니다.**

  // props.pagination이 없을 경우, 안전한 기본값을 설정
  const currentPageNo = pagination?.currentPageNo || 1;
  const totalRecordCount = pagination?.totalRecordCount || 0;
  const recordCountPerPage = pagination?.recordCountPerPage || 10;
  const pageSize = pagination?.pageSize || 10;

  // 2. 전체 페이지 수를 계산 (JSX에서 참조할 핵심 변수)
  const totalPageCount = Math.ceil(totalRecordCount / recordCountPerPage);

  if (!pagination) {
    paginationTag = <span>-</span>;
  } else {
    // 페이지 블록 계산 (페이지 번호 목록 생성에 사용)
    const currentFirstPage =
      Math.floor((currentPageNo - 1) / pageSize) * pageSize + 1;
    let currentLastPage = currentFirstPage + pageSize - 1;
    currentLastPage =
      currentLastPage > totalPageCount ? totalPageCount : currentLastPage;

    // 페이지 번호 목록 생성
    for (let i = currentFirstPage; i <= currentLastPage; i++) {
      if (i === currentPageNo) {
        // 현재 페이지
        const currentPage = (
          <div key={i}>
            <button className="num_on">
              <div className="num_on1"></div>
              {i}
            </button>
          </div>
        );
        paginationTag.push(currentPage);
      } else {
        // 다른 페이지
        const otherPage = (
          <div key={i}>
            <button
              className="num_off"
              onClick={() => {
                moveToPage(i);
              }}
            >
              {i}
            </button>
          </div>
        );
        paginationTag.push(otherPage);
      }
    }
  }

  console.log("paginationTag", paginationTag);
  console.groupEnd("EgovPaging");

  return (
    <div className="num_wrap d_flex d_jcc aic">
      {/* ◀️ 이전 페이지 화살표: currentPageNo - 1로 이동 */}
      <button className="num_l img_all"
        onClick={() => {
          // **유효한 currentPageNo 사용**
          if (currentPageNo > 1) {
            moveToPage(currentPageNo - 1);
          }
        }}
        // 현재 1페이지일 경우 비활성화 효과
        style={{ opacity: currentPageNo > 1 ? 1 : 0.5 }}
        tabIndex="0"
      >
      </button>

      {/* 🔢 페이지 번호 목록 렌더링 */}
      {paginationTag}

      {/* ▶️ 다음 페이지 화살표: currentPageNo + 1로 이동 */}
      <button className="num_r img_all"
        onClick={() => {
          // **유효한 currentPageNo와 totalPageCount 사용**
          if (currentPageNo < totalPageCount) {
            moveToPage(currentPageNo + 1);
          }
        }}
        // 마지막 페이지일 경우 비활성화 효과
        style={{ opacity: currentPageNo < totalPageCount ? 1 : 0.5 }}
        tabIndex="0"
      >
      </button>
    </div>
  );
};

export default EgovPaging;