import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovPaging from "@/components/EgovPaging";

import { itemIdxByPage } from "@/utils/calc";

interface Props {
  // Define any props here if needed
}

function EgovAdminMemberList(props: Props) {

  console.group("EgovAdminMemberList");
  console.log(
    "[Start] EgovAdminMemberMemberList ------------------------------"
  );
  console.log("EgovAdminMemberList [props] : ", props);

  const location = useLocation();
  console.log("EgovAdminMemberList [location] : ", location);

  const baseCondition: { [key: string]: any } = location.state?.searchCondition || {};

  // eslint-disable-next-line no-unused-vars
  const [searchCondition, setSearchCondition] = useState<{
    pageIndex: number;
    searchCnd: string;
    searchWrd: string;
  }>({
    // 1. 기본값으로 pageIndex: 1 설정
    pageIndex: 1,
    searchCnd: "0",
    searchWrd: "",
    // 2. location.state?.searchCondition이 있다면 덮어씁니다.
    ...baseCondition,
  }); // 기존 조회에서 접근 했을 시 || 신규로 접근 했을 시
  const [paginationInfo, setPaginationInfo] = useState<any>({});

  const cndRef = useRef<HTMLSelectElement>(null);
  const wrdRef = useRef<HTMLInputElement>(null);

  const [listTag, setListTag] = useState<(JSX.Element | null)[]>([]);

  const navigate = useNavigate();

  const handleRowClick = useCallback((item: { uniqId: string }) => {
    //  (item, srtitem) 인자 제거
    navigate(URL.ADMIN_MEMBERS_MODIFY, {
      state: {
        uniqId: item.uniqId,
        //  최신 searchCondition State를 참조합니다.
        searchCondition: searchCondition
      },
    });
    //  srtitem 인자 사용하지 않으므로 삭제
  }, [navigate, searchCondition]); //  deps에 searchCondition 포함

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
        (resp: { result: { paginationInfo: any; resultList: any[]; groupId_result: any[] } }) => {
          setPaginationInfo(resp.result.paginationInfo);
          setSearchCondition(srchCnd);

          let mutListTag: JSX.Element[] = [];
          // listTag.push(
          //   <tr>
          //     <td key="0" colSpan={6}>
          //       검색된 결과가 없습니다.
          //     </td>
          //   </tr>
          // ); // 목록 초기값
          const resultCnt = parseInt(resp.result.paginationInfo.totalRecordCount);
          const currentPageNo = resp.result.paginationInfo.currentPageNo;
          const pageSize = resp.result.paginationInfo.pageSize;
          // 리스트 항목 구성
          if (!resp.result.resultList || resp.result.resultList.length === 0) {
            mutListTag.push(
              // 수정] <p} 태그 대신 <tr} 태그 사용 (<tbody} 안에 들어가야 함)
              <tr key="0">
                <td colSpan={6} className="no_data">
                  검색된 결과가 없습니다.
                </td>
              </tr>
            );
          } else {
            resp.result.resultList.forEach(function (item: { mberId: string; mberNm: string; groupId: string; sbscrbDe: string; mberSttus: string }, index: number) {

              let authNm = "";
              resp.result.groupId_result.forEach((data: { code: string; codeNm: string }) => {
                if (data.code === item.groupId) authNm = data.codeNm;
              });

              // if (index === 0) mutListTag = []; // 목록 초기화
              const listIdx = itemIdxByPage(
                resultCnt,
                currentPageNo,
                pageSize,
                index
              );

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
          if (!mutListTag.length)
            mutListTag.push(
              <p className="no_data" key="0">
                검색된 결과가 없습니다.
              </p>
            ); // 회원 목록 초기값
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
    // 엔터 검색 시 조건 설정 및 retrieveList 호출
    retrieveList({
      ...searchCondition,
      pageIndex: 1, // 검색 시 첫 페이지로 이동
      searchCnd: cndRef.current?.value || "", // 현재 선택된 검색 유형
      searchWrd: wrdRef.current?.value || "", // 현재 입력된 검색어
    });
  };
  useEffect(() => {
    retrieveList(searchCondition);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
              <label className="font20" htmlFor="user_NAME">검색유형 선택</label>
              <select
                className="mid_sel"
                id="user_NAME"
                ref={cndRef}
                onChange={(e) => {
                  cndRef.current?.value = e.target.value;
                }}
              >
                <option value="0">사용자 ID</option>
                <option value="1">사용자 명</option>
              </select>
              <label htmlFor="user1" className="font20">검색어</label>
              <input
                id="user1"
                type="search"
                className="w390"
                placeholder="검색어를 입력하세요"
                defaultValue={searchCondition.searchWrd}
                ref={wrdRef}
                onChange={(e) => {
                  wrdRef.current?.value = e.target.value;
                }}
                onKeyDown={(e) => {
                  // 4. 엔터 키로 검색 기능 추가 
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
              <th className="txt_cen">사용자ID</th>
              <th className="txt_cen">사용자 명</th>
              <th className="txt_cen">권한 그룹</th>
              <th className="txt_cen">생성일</th>
              <th className="txt_cen">사용자 상태</th>
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
                  ...searchCondition, //  갱신 전 상태
                  pageIndex: passedPage, //  클릭된 새 페이지 번호
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
    </div >
  );
}

export default EgovAdminMemberList;