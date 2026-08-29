import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovRadioButtonGroup from "@/components/EgovRadioButtonGroup";

interface Props {
  mode: string;
}

interface ModeInfo {
  mode: string;
  modeTitle?: string;
  editURL?: string;
}

interface Detail {
  id?: string;
  resourceName?: string;
  uniqId?: string;
  [key: string]: any;
}

const EgovAdminDataAccessEdit: React.FC<Props & { location?: Location }> = (props) => {
  console.group("EgovAdminDataAccessEdit");
  console.log("[Start] EgovAdminDataAccessEdit ------------------------------");
  console.log("EgovAdminDataAccessEdit [props] : ", props);

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef<any[]>([]);

  console.log("EgovAdminDataAccessEdit [location] : ", location);
  const uniqId = location.state?.uniqId || "";
  
  const [modeInfo, setModeInfo] = useState.ModeInfo>({ mode: props.mode });
  const [detail, setDetail] = useState.Detail>({});

  const initMode = () => {
    switch (props.mode) {
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

  const retrieveDetail = () => {
    if (modeInfo.mode === CODE.MODE_MODIFY) {
      const retrieveDetailURL = `/dataaccess/update/${uniqId}`;
      const requestOptions = {
        method: "GET",
        headers: {
          "Content-type": "application/json",
        },
      };
      EgovNet.requestFetch(retrieveDetailURL, requestOptions, (resp: any) => {
        setDetail(resp.result.dataAccessVO);
      });
    }
  };

  const updateBoard = () => {
    let modeStr = modeInfo.mode === CODE.MODE_CREATE ? "POST" : "PUT";
    const requestOptions = {
      method: modeStr,
      headers: {
        "Content-type": "application/json",
      },
      body: JSON.stringify({ ...detail }),
    };

    EgovNet.requestFetch(modeInfo.editURL, requestOptions, (resp: any) => {
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

  const deleteBoard = (uniqId: string) => {
    const deleteURL = `/dataaccess/delete/${uniqId}`;

    const requestOptions = {
      method: "DELETE",
      headers: {
        "Content-type": "application/json",
      },
    };

    EgovNet.requestFetch(deleteURL, requestOptions, (resp: any) => {
      console.log("====>>> board delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        alert("게시물이 삭제되었습니다.");
        navigate(URL.ADMIN_DATAACCESS, { replace: true });
      } else {
        alert("ERR : " + resp.resultMessage);
      }
    });
  };

  useEffect(() => {
    initMode();
  }, []);

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
            <li>{modeInfo.mode === CODE.MODE_CREATE ? "데이터 접근권한 등록" : "데이터 접근권한 수정"}</li>
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
                    <dt>{detail.id ? "권한 ID" : ""}</dt>
                    <dd>{detail.id}</dd>
                </dl>
                <dl>
                    <dt>{detail.resourceName ? "리소스명" : ""}</dt>
                    <dd>{detail.resourceName}</dd>
                </dl>
                {/* Add more fields as needed based on actual data structure */}
            </div>

            <div className="board_btn_area">
              <div className="left_col btn1">
                <button
                  className="btn btn_skyblue_h46 w_100"
                  onClick={() => updateBoard()}
                >
                  저장
                </button>
                {modeInfo.mode === CODE.MODE_MODIFY && (
                  <button
                    className="btn btn_skyblue_h46 w_100"
                    onClick={() => {
                      deleteBoard(detail.uniqId);
                    }}
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
};

export default EgovAdminDataAccessEdit;