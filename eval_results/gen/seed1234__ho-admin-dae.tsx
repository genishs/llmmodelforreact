import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovRadioButtonGroup from "@/components/EgovRadioButtonGroup";

interface Props { mode: string; }

function EgovAdminDataAccessEdit({ mode }: Props): JSX.Element {
  console.group("EgovAdminDataAccessEdit");
  console.log("[Start] EgovAdminDataAccessEdit ------------------------------");
  console.log("EgovAdminDataAccessEdit [props] : ", { mode });

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef<React.RefObject<HTMLInputElement>[]>([]);

  console.log("EgovAdminDataAccessEdit [location] : ", location);
  const uniqId = location.state?.uniqId || "";

  const [modeInfo, setModeInfo] = useState<{ mode: string; modeTitle?: string; editURL?: string }>({ mode });
  const [detail, setDetail] = useState<{ [key: string]: any }>({});

  const initMode = (): void => {
    switch (mode) {
      case CODE.MODE_CREATE:
        setModeInfo({
          ...modeInfo,
          modeTitle: "등록",
          editURL: "/dataaccess/insert",
        });
        break;

      case CODE.MODE_MODIFY:
        setModeInfo({
          ...modeInfo,
          modeTitle: "수정",
          editURL: `/dataaccess/update`,
        });
        break;
      default:
        navigate({ pathname: URL.ERROR }, { state: { msg: "" } });
    }
    retrieveDetail();
  };

  const retrieveDetail = (): void => {
    if (modeInfo.mode === CODE.MODE_MODIFY) {
      const retrieveDetailURL = `/dataaccess/update/${uniqId}`;
      const requestOptions: RequestInit = {
        method: "GET",
        headers: {
          "Content-type": "application/json",
        },
      };
      EgovNet.requestFetch(retrieveDetailURL, requestOptions, (resp: { result: { dataAccessVO: { [key: string]: any }; }; }) => {
        setDetail(resp.result.dataAccessVO);
      });
    }
  };

  const updateBoard = (): void => {
    let modeStr = modeInfo.mode === CODE.MODE_CREATE ? "POST" : "PUT";
    const requestOptions: RequestInit = {
        method: modeStr,
        headers: {
            "Content-type": "application/json",
        },
        body: JSON.stringify({ ...detail }),
    };

    EgovNet.requestFetch(modeInfo.editURL, requestOptions, (resp: { resultCode: number; resultMessage: string; }) => {
        if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
            navigate({ pathname: URL.ADMIN_DATAACCESS });
        } else {
            navigate(
            { pathname: URL.ERROR },
            { state: { msg: resp.resultMessage } }
            );
        }
    });
  };

  const deleteBoard = (uniqId: string): void => {
    const deleteURL = `/dataaccess/delete/${uniqId}`;

    const requestOptions: RequestInit = {
      method: "DELETE",
      headers: {
        "Content-type": "application/json",
      },
    };

    EgovNet.requestFetch(deleteURL, requestOptions, (resp: { resultCode: number; resultMessage: string; }) => {
      console.log("====>>> board delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        alert("게시물이 삭제되었습니다.");
        navigate(URL.ADMIN_DATAACCESS, { replace: true });
      } else {
        alert("ERR : " + resp.resultMessage);
      }
    });
  };

  useEffect((): void => {
    initMode();
  }, [mode]);

  return (
    <div className="container">
      <div className="c_wrap">
        <div className="location">
          <ul>
            <li>
              <Link to={URL.MAIN} className="home">
                Home
              </Link>
            </li>
            <li>
              <Link to={URL.ADMIN}>사이트관리</Link>
            </li>
            <li>데이터 접근권한 관리</li>
          </ul>
        </div>

        <div className="layout">
          <EgovLeftNav></EgovLeftNav>
          <div className="contents BOARD_CREATE_REG" id="contents">
            <div className="top_tit">
              <h1 className="tit_1">사이트관리</h1>
            </div>

            {modeInfo.mode === CODE.MODE_CREATE && (
              <h2 className="tit_2">데이터 접근권한 등록</h2>
            )}

            {modeInfo.mode === CODE.MODE_MODIFY && (
              <h2 className="tit_2">데이터 접근권한 수정</h2>
            )}

            <div className="board_view2">
                {/* Dummy Fields for DataAccess */}
                <dl>
                    <dt>권한 ID</dt>
                    <dd>{detail.id}</dd>
                </dl>
                <dl>
                    <dt>리소스명</dt>
                    <dd>{detail.resourceName}</dd>
                </dl>
                {/* Add more fields as needed based on actual data structure */}
            </div>

            <div className="board_btn_area">
              <div className="left_col btn1">
                <button
                  className="btn btn_skyblue_h46 w_100"
                  onClick={updateBoard}
                >
                  저장
                </button>
                {modeInfo.mode === CODE.MODE_MODIFY && (
                  <button
                    className="btn btn_skyblue_h46 w_100"
                    onClick={() => deleteBoard(detail.uniqId)}
                  >
                    삭제
                  </button>
                )}
              </div>

              <div className="right_col btn1">
                <Link
                  to={URL.ADMIN_DATAACCESS}
                  className="btn btn_blue_h46 w_100"
                >
                  목록
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EgovAdminDataAccessEdit;