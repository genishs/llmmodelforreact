import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovPaging from "@/components/EgovPaging";

interface SearchCondition {
  pageIndex: number;
  searchCnd: string;
  searchWrd: string;
}

interface PaginationInfo {
  totalRecordCount: number;
  currentPageNo: number;
  pageSize: number;
}

function EgovAdminMemberList(): JSX.Element {
  const location = useLocation();
  const baseCondition: SearchCondition = location.state?.searchCondition || {};
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

  const handleRowClick = useCallback((item: { uniqId: string }) => {
    navigate(URL.ADMIN_MEMBERS_MODIFY, {
      state: { uniqId: item.uniqId, searchCondition },
    });
  }, [navigate, searchCondition]);

  const retrieveList = useCallback(async (srchCnd: SearchCondition): Promise<void> => {
    const retrieveListURL = "/members" + EgovNet.getQueryString(srchCnd);
    const requestOptions: RequestInit = {
      method: "GET",
      headers: { "Content-type": "application/json" },
    };
    try {
      const resp = await EgovNet.requestFetch(retrieveListURL, requestOptions);
      setPaginationInfo(resp.result.paginationInfo);
      setSearchCondition(srchCnd);
      const resultList = resp.result.resultList ?? [];
      const mutListTag: JSX.Element[] = resultList.map((item, index) => {
        const authNm = resp.result.groupId_result.find((data) => data.code === item.groupId)?.codeNm ?? "";
        const listIdx = itemIdxByPage(parseInt(resp.result.paginationInfo.totalRecordCount), srchCnd.pageIndex, resp.result.paginationInfo.pageSize, index);
        return (
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
      if (mutListTag.length === 0) {
        mutListTag.push(<tr key="0"><td colSpan={6} className="no_data">검색된 결과가 없습니다.</td></tr>);
      }
      setListTag(mutListTag);
    } catch (error) {
      console.error(error);
    }
  }, [handleRowClick]);

  const handleSearch = (): void => {
    retrieveList({
      ...searchCondition,
      pageIndex: 1,
      searchCnd: cndRef.current?.value ?? "",
      searchWrd: wrdRef.current?.value ?? "",
    });
  };

  useEffect(() => {
    retrieveList(searchCondition);
  }, [searchCondition, retrieveList]);

  return (
    <div id="new_wrap2">
      {/* ... */}
    </div>
  );
}

export default EgovAdminMemberList;