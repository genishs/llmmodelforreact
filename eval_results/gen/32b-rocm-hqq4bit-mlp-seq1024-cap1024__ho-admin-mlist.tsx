import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovPaging from "@/components/EgovPaging";

import { itemIdxByPage } from "@/utils/calc";

interface SearchCondition {
  pageIndex?: number;
  searchCnd?: string;
  searchWrd?: string;
}

interface PaginationInfo {
  totalRecordCount: number;
  currentPageNo: number;
  pageSize: number;
}

interface GroupData {
  code: string;
  codeNm: string;
}

interface MemberItem {
  uniqId: string;
  mberId: string;
  mberNm: string;
  groupId: string;
  sbscrbDe: string;
  mberSttus: string;
}

interface ResultResponse {
  resultList: MemberItem[];
  groupId_result: GroupData[];
  paginationInfo: PaginationInfo;
}

function EgovAdminMemberList() {
  const location = useLocation();
  const baseCondition = location.state?.searchCondition || {};
  const [searchCondition, setSearchCondition] = useState<SearchCondition>({
    pageIndex: 1,
    searchCnd: "0",
    searchWrd: "",
    ...baseCondition,
  });
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo>({});
  const cndRef = useRef<HTMLSelectElement>(null);
  const wrdRef = useRef<HTMLInputElement>(null);
  const [listTag, setListTag] = useState<JSX.Element[]>([]);
  const navigate = useNavigate();

  const handleRowClick = useCallback((item: MemberItem) => {
    navigate(URL.ADMIN_MEMBERS_MODIFY, {
      state: {
        uniqId: item.uniqId,
        searchCondition: searchCondition,
      },
    });
  }, [navigate, searchCondition]);

  const retrieveList = useCallback(async (srchCnd: SearchCondition) => {
    try {
      const retrieveListURL = `/members${EgovNet.getQueryString(srchCnd)}`;
      const requestOptions = {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      };
      const resp = await EgovNet.requestFetch(retrieveListURL, requestOptions);
      if (resp.status !== 200) throw new Error(`HTTP error! status: ${resp.status}`);
      const data = await resp.json();
      setPaginationInfo(data.result.paginationInfo);
      setSearchCondition(srchCnd);
      let mutListTag: JSX.Element[] = [];

      const resultCnt = parseInt(data.result.paginationInfo.totalRecordCount);
      const currentPageNo = data.result.paginationInfo.currentPageNo;
      const pageSize = data.result.paginationInfo.pageSize;

      if (!data.result.resultList || data.result.resultList.length === 0) {
        mutListTag.push(
          <tr key="0">
            <td colSpan={6} className="no_data">
              검색된 결과가 없습니다.
            </td>
          </tr>
        );
      } else {
        data.result.resultList.forEach((item: MemberItem, index: number) => {
          let authNm = "";
          data.result.groupId_result.forEach((data: GroupData) => {
            if (data.code === item.groupId) authNm = data.codeNm;
          });

          const listIdx = itemIdxByPage(resultCnt, currentPageNo, pageSize, index);
          mutListTag.push(
            <tr key={listIdx} onClick={() => handleRowClick(item)}>
              <td>{listIdx}</td>
              <td>{item.mberId}</td>
              <td>{item.mberNm}</td>
              <td>{authNm}</td>
              <td>{item.sbscrbDe}</td>
              <td>{item.mberSttus === "P" ? "가능" : item.mberSttus === "A" ? "대기" : "탈퇴"}</td>
            </tr>
          );
        });
      }

      setListTag(mutListTag);
    } catch (error) {
      console.error(error);
    }
  }, [handleRowClick]);

  const handleSearch = () => {
    retrieveList({
      ...searchCondition,
      pageIndex: 1,
      searchCnd: cndRef.current!.value,
      searchWrd: wrdRef.current!.value,
    });
  };

  useEffect(() => {
    retrieveList(searchCondition);
  }, [retrieveList, searchCondition]);

  return (
    <div id="new_wrap2">
      {/* 중략 */}
      <div className="mid_find d_flex d_jcc aic">
        <label className="font20" htmlFor="user_name">검색유형 선택</label>
        <select className="mid_sel"
          id="user_name"
          ref={cndRef}
          onChange={(e) => {
            cndRef.current!.value = e.target.value;
          }}>
          <option value="0">사용자 ID</option>
          <option value="1">사용자 명</option>
        </select>
        <label htmlFor="user1" className="font20">검색어</label>
        <input
          id="user1"
          type="search"
          className="w390"
          placeholder="검색어를 입력하세요"
          defaultValue={searchCondition && searchCondition.searchWrd}
          ref={wrdRef}
          onChange={(e) => {
            wrdRef.current!.value = e.target.value;
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSearch();
            }
          }}
        />
        <Link href="#" to={URL.ADMIN_MEMBERS_CREATE}>
          <div className="blu_btn">등 록</div>
        </Link>
      </div>
      {/* 중략 */}
      <table className="board">
        <colgroup>
          <col width="5%" />
          <col width="15%" />
          <col width="15%" />
          <col width="20%" />
          <col width="20%" />
          <col width="15%" />
        </colgroup>
        <thead>
          <tr>
            <th>No</th>
            <th>사용자ID</th>
            <th>사용자 명</th>
            <th>권한 그룹</th>
            <th>생성일</th>
            <th>사용자 상태</th>
          </tr>
        </thead>
        <tbody>
          {listTag}
        </tbody>
      </table>
      {/* 중략 */}
    </div>
  );
}

export default EgovAdminMemberList;