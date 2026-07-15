import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovPaging from "@/components/EgovPaging";

import { itemIdxByPage } from "@/utils/calc";

interface Props {
  // Define your props here
}

function EgovAdminMemberList(props: Props) {
  console.group("EgovAdminMemberList");
  console.log("[Start] EgovAdminMemberList ------------------------------");
  console.log("EgovAdminMemberList [props] : ", props);

  const location = useLocation();
  console.log("EgovAdminMemberList [location] : ", location);

  const baseCondition = location.state?.searchCondition || {};

  const [searchCondition, setSearchCondition] = useState<{
    pageIndex: number;
    searchCnd: string;
    searchWrd: string;
  }>({
    pageIndex: 1,
    searchCnd: "0",
    searchWrd: "",
    ...baseCondition,
  });

  const [paginationInfo, setPaginationInfo] = useState<{}>({});
  const cndRef = useRef<HTMLSelectElement>(null);
  const wrdRef = useRef<HTMLInputElement>(null);
  const [listTag, setListTag] = useState<JSX.Element[]>([]);
  const navigate = useNavigate();

  const handleRowClick = useCallback((item: any) => {
    navigate(URL.ADMIN_MEMBERS_MODIFY, {
      state: {
        uniqId: item.uniqId,
        searchCondition: searchCondition,
      },
    });
  }, [navigate, searchCondition]);

  const retrieveList = useCallback(
    (srchCnd: { pageIndex: number; searchCnd: string; searchWrd: string }) => {
      console.groupCollapsed("EgovAdminMemberList.retrieveList()");
      const retrieveListURL = "/members" + EgovNet.getQueryString(srchCnd);

      const requestOptions = {
        method: "GET",
        headers: {
          "Content-type": "application/json",
        },
      };

      EgovNet.requestFetch(
        retrieveListURL,
        requestOptions,
        (resp: any) => {
          setPaginationInfo(resp.result.paginationInfo);
          setSearchCondition(srchCnd);

          let mutListTag: JSX.Element[] = [];
          const resultCnt = parseInt(resp.result.paginationInfo.totalRecordCount);
          const currentPageNo = resp.result.paginationInfo.currentPageNo;
          const pageSize = resp.result.paginationInfo.pageSize;

          if (!resp.result.resultList || resp.result.resultList.length === 0) {
            mutListTag.push(
              <tr key="0">
                <td colSpan={6} className="no_data">
                  검색된 결과가 없습니다.
                </td>
              </tr>
            );
          } else {
            resp.result.resultList.forEach((item: any, index: number) => {
              let authNm = "";
              resp.result.groupId_result.forEach((data: any) => {
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
                  <td>
                    {item.mberSttus === "P" ? "가능" : item.mberSttus === "A" ? "대기" : "탈퇴"}
                  </td>
                </tr>
              );
            });
          }

          if (!mutListTag.length)
            mutListTag.push(
              <p className="no_data" key="0">
                검색된 결과가 없습니다.
              </p>
            );
          setListTag(mutListTag);
        },
        (resp: any) => {
          console.log("err response : ", resp);
        }
      );
      console.groupEnd("EgovAdminMemberList.retrieveList()");
    },
    [setPaginationInfo, setSearchCondition, setListTag, handleRowClick]
  );

  const handleSearch = () => {
    retrieveList({
      ...searchCondition,
      pageIndex: 1,
      searchCnd: cndRef.current?.value || "",
      searchWrd: wrdRef.current?.value || "",
    });
  };

  useEffect(() => {
    retrieveList(searchCondition);
  }, [searchCondition]);

  console.log("------------------------------EgovAdminMemberList [End]");
  console.groupEnd("EgovAdminMemberList");

  return (
    <div id="new_wrap2">
      <div className="mid_wrap d_flex d_jcc">
        <div className="w1200">
          <div className="nav_wrap d_flex d_end">
            <div className="nav d_flex d_end">
              <Link to={URL.MAIN}><div className="nav_ico img_all"></div></Link>
              <div className="nav_ico_arr img_all"></div>
              <Link to={URL.ADMIN}><div className="nav_txt">시스템 운영관리</div></Link>
              <div className="nav_ico_arr img_all"></div>
              <Link><div className="nav_txt">사용자 관리</div></Link>
            </div>
          </div>
          <div>
            <h1 className="txt_cen">사용자 관리</h1>
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
          </div>
        </div>
      </div>

      <div className="bor_wrap d_flex d_jcc">
        <div className="bor_in1">
          <table className="board">
            <colgroup>
              <col width="5%" />
              <col width="15%" />
              <col width="15%" />
              <col width="20%" />
              <col width="20%" />
              <col width="15%" />
            </colgroup>
            <tr>
              <th>No</th>
              <th>사용자ID</th>
              <th>사용자 명</th>
              <th>권한 그룹</th>
              <th>생성일</th>
              <th>사용자 상태</th>
            </tr>
            <tbody>
              {listTag}
            </tbody>
          </table>
          <div className="num_wrap d_flex d_jcc aic">
            <EgovPaging
              pagination={paginationInfo}
              moveToPage={(passedPage: number) => {
                const nextSearchCondition = {
                  ...searchCondition,
                  pageIndex: passedPage,
                  searchCnd: cndRef.current?.value || "",
                  searchWrd: wrdRef.current?.value || "",
                };

                console.log("Log 1: 최종 API 호출 인자:", nextSearchCondition);

                retrieveList(nextSearchCondition);
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default EgovAdminMemberList;