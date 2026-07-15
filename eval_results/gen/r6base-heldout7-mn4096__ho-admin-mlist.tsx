import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

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
  const location = useLocation<SearchCondition>();
  const [searchCondition, setSearchCondition] = useState<SearchCondition>({
    pageIndex: 1,
    searchCnd: "0",
    searchWrd: "",
    ...location.state?.searchCondition,
  });
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo>({ totalRecordCount: 0, currentPageNo: 1, pageSize: 10 });
  const cndRef = useRef<HTMLSelectElement>(null);
  const wrdRef = useRef<HTMLInputElement>(null);
  const [listTag, setListTag] = useState<JSX.Element[]>([]);
  const navigate = useNavigate();

  const handleRowClick = useCallback((item: { uniqId: string }) => {
    navigate(URL.ADMIN_MEMBERS_MODIFY, { state: { uniqId: item.uniqId, searchCondition } });
  }, [navigate, searchCondition]);

  const retrieveList = useCallback(async (srchCnd: SearchCondition): Promise<void> => {
    const retrieveListURL = `/members${EgovNet.getQueryString(srchCnd)}`;
    const requestOptions = { method: "GET", headers: { "Content-type": "application/json" } };
    try {
      const resp = await EgovNet.requestFetch(retrieveListURL, requestOptions);
      setPaginationInfo(resp.result.paginationInfo);
      setSearchCondition(srchCnd);
      const resultList = resp.result.resultList ?? [];
      const mutListTag = resultList.map((item, index) => {
        const listIdx = itemIdxByPage(paginationInfo.totalRecordCount, srchCnd.pageIndex, paginationInfo.pageSize, index);
        return (
          <tr key={listIdx} onClick={() => handleRowClick(item)}>
            <td>{listIdx}</td>
            <td>{item.mberId}</td>
            <td>{item.mberNm}</td>
            <td>{item.authNm}</td>
            <td>{item.sbscrbDe}</td>
            <td>{item.mberSttus === "P" ? "가능" : item.mberSttus === "A" ? "대기" : "탈퇴"}</td>
          </tr>
        );
      });
      if (mutListTag.length === 0) {
        mutListTag.push(<tr key="0"><td colSpan={6}>검색된 결과가 없습니다.</td></tr>);
      }
      setListTag(mutListTag);
    } catch (error) {
      console.error("Error fetching member list:", error);
    }
  }, [setPaginationInfo, setSearchCondition, setListTag, handleRowClick, paginationInfo]);

  const handleSearch = (): void => {
    retrieveList({ ...searchCondition, pageIndex: 1, searchCnd: cndRef.current?.value ?? "", searchWrd: wrdRef.current?.value ?? "" });
  };

  useEffect(() => { retrieveList(searchCondition); }, [searchCondition, retrieveList]);

  return (
    <div id="new_wrap2">
      {/* ... */}
    </div>
  );
}

export default EgovAdminMemberList;