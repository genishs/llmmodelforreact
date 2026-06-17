# -*- coding: utf-8 -*-
"""
egovGeoportal 실파일 JS→TS 변환 학습쌍 생성 (B 레버: 배포 분포 일치 데이터).

입력(.jsx)은 실제 프로젝트에서 읽고, 출력(.tsx)은 큐레이션한 고품질 변환을 쓴다.
지시문은 파일명을 포함해 고유 → 합성 로더의 지시문 dedup을 통과한다.
★ eval_harness가 쓰는 파일(EgovPaging.jsx, EgovDownloadDetail.jsx)은 학습/평가 오염 방지로 제외.

출력: data/handcrafted_synth_egovreal.jsonl  (build_dataset_v2의 glob에 포함됨)
실행: python scripts/build_egov_pairs.py
"""
import json
from pathlib import Path

EGOV = Path("d:/Documents/workspace/TwinSpace/egovGeoportal/src")
OUT = Path("./data/handcrafted_synth_egovreal.jsonl")

INSTR = ("다음 React 컴포넌트({name}.jsx)를 TypeScript(.tsx)로 변환해줘. "
         "props가 있으면 interface로 정의하고, 훅/이벤트/상태에 타입을 명시해줘.")

# name -> (상대경로, 큐레이션한 .tsx 출력)
PAIRS = {
"EgovCondition": ("components/EgovCondition.jsx", '''import { Link } from "react-router-dom";

function EgovCondition(): JSX.Element {
  return (
    <div className="condition">
      <ul>
        <li>
          <label className="f_select" htmlFor="sel1">
            <select name="" id="sel1" title="조건">
              <option value="">전체</option>
              <option value="1">회의</option>
              <option value="2">세미나</option>
              <option value="3">강의</option>
              <option value="4">교육</option>
              <option value="5">기타</option>
            </select>
          </label>
        </li>
        <li>
          <Link to="" className="prev">이전연도로이동</Link>
          <span>2021년</span>
          <Link to="" className="next">다음연도로이동</Link>
        </li>
        <li className="half L">
          <Link to="" className="prev">이전월로이동</Link>
          <span>8월</span>
          <Link to="" className="next">다음월로이동</Link>
        </li>
        <li className="half R">
          <Link to="" className="prev">이전주로이동</Link>
          <span>1주</span>
          <Link to="" className="next">다음주로이동</Link>
        </li>
      </ul>
    </div>
  );
}

export default EgovCondition;'''),

"EgovInfoPopup": ("components/EgovInfoPopup.jsx", '''import templateIntroImg from "/assets/images/img_template_intro.png";

function EgovInfoPopup(): JSX.Element {
  return (
    <div className="wrap_pop TEMPLATE_INTRO">
      <div className="pop_inner">
        <div className="pop_header">
          <h1>홈페이지 템플릿 소개</h1>
          <button className="btn close" type="button">
            닫기
          </button>
        </div>

        <div className="pop_container">
          <ul className="list_1">
            <li>
              경량환경 템플릿은 개발자가 프레임워크 쉽게 이해하고 활용할 수
              있도록 지원합니다.
            </li>
            <li>
              홈페이지 템플릿은 공통컴포넌트를 기반으로 아래 그림과 같이 메뉴가
              구성됩니다.
            </li>
            <li>
              관리자로 로그인하면 관리자용 메뉴를 추가로 사용할 수 있습니다.
            </li>
            <li>
              사이트소개, 정보마당, 고객지원 메뉴는 구성을 위한 샘플페이지가
              제공되며 기능은 구현되지 않은 상태입니다.
            </li>
          </ul>
          <div className="img">
            <img src={templateIntroImg} alt="" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default EgovInfoPopup;'''),

"EgovLeftNavSupport": ("components/leftmenu/EgovLeftNavSupport.jsx", '''import { NavLink } from "react-router-dom";
import URL from "@/constants/url";

function EgovLeftNavSupport(): JSX.Element {
  return (
    <div className="nav">
      <div className="inner">
        <h2>고객지원</h2>
        <ul className="menu4">
          <li>
            <NavLink
              to={URL.SUPPORT_DOWNLOAD}
              className={({ isActive }: { isActive: boolean }) => (isActive ? "cur" : "")}
            >
              자료실
            </NavLink>
          </li>
          <li>
            <NavLink
              to={URL.SUPPORT_QNA}
              className={({ isActive }: { isActive: boolean }) => (isActive ? "cur" : "")}
            >
              묻고답하기
            </NavLink>
          </li>
          <li>
            <NavLink
              to={URL.SUPPORT_APPLY}
              className={({ isActive }: { isActive: boolean }) => (isActive ? "cur" : "")}
            >
              서비스신청
            </NavLink>
          </li>
        </ul>
      </div>
    </div>
  );
}

export default EgovLeftNavSupport;'''),

"EgovChart": ("pages/chart/EgovChart.jsx", '''import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavChart";
import { getchartData } from "@/api/store/slice/geopotalSlice";

interface ChartState {
  chartdata: unknown[];
}

function EgovChart(): JSX.Element {
  const dispatch = useDispatch();
  const { chartdata } = useSelector(
    (state: { geopotalRedycer: ChartState }) => state.geopotalRedycer
  );

  useEffect(() => {
    if (chartdata.length === 0) dispatch(getchartData());
  }, []);

  return (
    <div className="container">
      <div className="c_wrap">
        <div className="layout">
          <EgovLeftNav></EgovLeftNav>
          <div className="chart_title">
            <h1>앱별 이용현황</h1>
            <p className="txt_1">소개텍스트</p>
          </div>
          <div className="chartArea_wrap">
            <div className="chart_search">
              <input />
            </div>
            <div className="chartArea">
              <div className="line_area"></div>
              <div className="circle_area"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EgovChart;'''),

"SnsKakaoCallback": ("components/sns/SnsKakaoCallback.jsx", '''import { useEffect } from "react";
import * as EgovNet from "@/api/egovFetch";
import CODE from "@/constants/code";
import { setSessionItem } from "@/utils/storage";

interface LoginResp {
  resultVO: unknown;
  jToken?: string | null;
  resultCode: string | number;
}

const SnsKakaoCallback = (): JSX.Element => {
  const callBackEnd = (): void => {
    const code = new URL(window.location.href).searchParams.get("code");
    const state = new URL(window.location.href).searchParams.get("state");
    console.log("code, state=====>", code, state);
    if (code) {
      const kakaoLoginUrl = `/login/kakao/callback?code=${code}&state=${state}`;
      const requestOptions: RequestInit = {
        method: "GET",
        headers: { "Content-type": "application/json" },
      };
      EgovNet.requestFetch(kakaoLoginUrl, requestOptions, (resp: LoginResp) => {
        const resultVO = resp.resultVO;
        const jToken = resp?.jToken || null;
        if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
          setSessionItem("jToken", jToken);
          setSessionItem("loginUser", resultVO);
          document.querySelector(".all_menu.WEB")?.classList.add("closed");
          document.querySelector(".btnAllMenu")?.classList.remove("active");
          const allMenuBtn = document.querySelector(".btnAllMenu") as HTMLElement | null;
          if (allMenuBtn) allMenuBtn.title = "전체메뉴 닫힘";
          document.querySelector(".all_menu.Mobile")?.classList.add("closed");
          alert("Sns 간편 로그인 중...");
        } else {
          window.location.replace("/");
        }
      });
    }
  };
  useEffect(callBackEnd, []);

  return (
    <>
      <h1 className="btn_social">로그인 중...</h1>
    </>
  );
};

export default SnsKakaoCallback;'''),

"EgovError": ("components/EgovError.jsx", '''import { useNavigate, useLocation } from "react-router-dom";

interface ErrorLocationState {
  msg?: string;
}

function EgovError(): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();

  const state = location.state as ErrorLocationState | null;
  let errormessage = state?.msg || "알 수 없는 에러가 발생했습니다.";

  if (errormessage === "No message available") {
    errormessage = "알 수 없는 에러가 발생했습니다.";
  }

  const goBack = (): void => {
    navigate(-1, { replace: true });
  };

  return (
    <div className="ERROR">
      <h1>Error</h1>
      <div className="box">
        <p>{errormessage}</p>
        <div className="btn_area">
          <button className="btn btn_blue_h46 w_130" onClick={goBack}>
            이전페이지
          </button>
        </div>
      </div>
    </div>
  );
}

export default EgovError;'''),

"PrivateRoutes": ("routes/PrivateRoutes.jsx", '''import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import URL from "@/constants/url";
import * as EgovNet from "@/api/egovFetch";

const PrivateRoutes = (): JSX.Element | null => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const location = useLocation();

  useEffect(() => {
    const jwtAuthURL = "/jwtAuthAPI";
    const requestOptions: RequestInit = { method: "POST" };

    EgovNet.requestFetch(jwtAuthURL, requestOptions, (resp: unknown) => {
      setIsAuthenticated(resp !== false);
    });
  }, []);

  if (isAuthenticated === null) {
    return null;
  }

  return isAuthenticated ? <Outlet /> : <Navigate to={URL.LOGIN} state={{ from: location }} />;
};

export default PrivateRoutes;'''),

"EgovAboutSite": ("pages/about/EgovAboutSite.jsx", '''import img_1 from "/assets/images/ori_ico_bn03.png";
import img_2 from "/assets/images/ori_ico_bn04.png";
import img_3 from "/assets/images/ori_ico_bn01.png";

interface SiteItem {
  title: string;
  url: string;
  img: string;
}

function EgovAboutSite(): JSX.Element {
  const list: SiteItem[] = [
    { title: "사용자 관리", url: "", img: img_1 },
    { title: "데이터 접근권한 관리", url: "", img: img_2 },
    { title: "플랫폼 이용현황", url: "", img: img_3 },
  ];

  const setBox = (): JSX.Element => {
    return (
      <>
        {list.map((e, i) => (
          <div className="b1" key={i}>
            <div className="b1_title">
              <h3>{e.title}</h3>
            </div>
            <div className="b1_img">
              <img src={e.img} alt={e.title} />
            </div>
          </div>
        ))}
      </>
    );
  };

  return (
    <div className="container">
      <div className="c_wrap">
        <div className="layout">
          <div className="system_layout">{setBox()}</div>
        </div>
      </div>
    </div>
  );
}

export default EgovAboutSite;'''),

"AdminNoticeCreatePopup": ("pages/admin/notice/AdminNoticeCreatePopup.jsx", '''import React from "react";

interface BoardDetail {
  bbsId?: string;
  nttId?: string;
  nttSj?: string;
  nttCn?: string;
}

interface AdminNoticeCreatePopupProps {
  onClose: () => void;
  boardDetail: BoardDetail;
  setBoardDetail: (detail: BoardDetail) => void;
  updateBoard: () => void;
  deleteBoard: (bbsId?: string, nttId?: string) => void;
}

function AdminNoticeCreatePopup({
  onClose,
  boardDetail,
  setBoardDetail,
  updateBoard,
  deleteBoard,
}: AdminNoticeCreatePopupProps): JSX.Element {
  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const value = e.target.value;
    setBoardDetail({
      ...boardDetail,
      nttSj: value,
      nttCn: value,
    });
  };

  const isEditMode = boardDetail && boardDetail.nttId;

  return (
    <div className="popup_bg">
      <div className="popup">
        <div>
          <div className="pop_title sbold tac d_flex d_jcc">
            {isEditMode ? "공지사항 수정" : "공지사항 등록"}
          </div>
          <a href="#" onClick={onClose}>
            <div className="pop_x img_all"></div>
          </a>
        </div>

        <div className="pop_input_wrap d_flex aic">
          <label htmlFor="nttSj" className="pop_txt">내 용</label>
          <input
            className="pop_input"
            id="nttSj"
            name="nttSj"
            type="text"
            value={boardDetail.nttSj || ""}
            onChange={handleTitleChange}
          />
        </div>

        <div className="pop_btn_wrap">
          <div className="blu_btn" onClick={updateBoard} role="button" tabIndex={0}>
            저 장
          </div>
          {isEditMode && (
            <div
              className="blu_btn"
              onClick={() => deleteBoard(boardDetail.bbsId, boardDetail.nttId)}
              role="button"
              tabIndex={0}
            >
              삭 제
            </div>
          )}
          <div className="w_btn" onClick={onClose} role="button" tabIndex={0}>
            취 소
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminNoticeCreatePopup;'''),

"EgovLeftNavInform": ("components/leftmenu/EgovLeftNavInform.jsx", '''import { NavLink } from "react-router-dom";
import URL from "@/constants/url";

function EgovLeftNavInform(): JSX.Element {
  return (
    <div className="nav">
      <div className="inner">
        <h2>알림마당</h2>
        <ul className="menu4">
          <li>
            <NavLink
              to={URL.INFORM_NOTICE}
              className={({ isActive }: { isActive: boolean }) => (isActive ? "cur" : "")}
            >
              공지사항
            </NavLink>
          </li>
          <li style={{ display: "none" }}>
            <NavLink
              to={URL.INFORM_DAILY}
              className={({ isActive }: { isActive: boolean }) => (isActive ? "cur" : "")}
            >
              오늘의행사
            </NavLink>
          </li>
          <li style={{ display: "none" }}>
            <NavLink
              to={URL.INFORM_WEEKLY}
              className={({ isActive }: { isActive: boolean }) => (isActive ? "cur" : "")}
            >
              금주의행사
            </NavLink>
          </li>
          <li style={{ display: "none" }}>
            <NavLink
              to={URL.INFORM_GALLERY}
              className={({ isActive }: { isActive: boolean }) => (isActive ? "cur" : "")}
            >
              사이트갤러리
            </NavLink>
          </li>
        </ul>
      </div>
    </div>
  );
}

export default EgovLeftNavInform;'''),
}


def main():
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for name, (rel, output) in PAIRS.items():
            src = EGOV / rel
            code = src.read_text(encoding="utf-8")
            rec = {"instruction": INSTR.format(name=name), "input": code, "output": output}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"[완료] {n}개 실파일 변환쌍 → {OUT}")


if __name__ == "__main__":
    main()
