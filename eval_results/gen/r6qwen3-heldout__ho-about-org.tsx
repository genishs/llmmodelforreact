import { Link } from 'react-router-dom';

interface Props {}

const URL = {
  MAIN: '/',
  ABOUT: '/about',
};

function EgovAboutOrganization({}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="container">
      <div className="c_wrap">
        <div className="location">
          <ul>
            <li><Link to={URL.MAIN} className="home">Home</Link></li>
            <li><Link to={URL.ABOUT}>사이트 소개</Link></li>
            <li>조직소개</li>
          </ul>
        </div>

        <div className="layout">
          <aside style={{ width: open ? 200 : 60 }}>
            <button onClick={() => setOpen((o) => !o)}>≡</button>
            <nav>{/* 네비게이션 메뉴 */}</nav>
          </aside>
          <main style={{ flex: 1, padding: 20 }}>
            <header>
              <h1 className="tit_3">사이트 소개</h1>
              <p className="txt_1">표준프레임워크 경량환경 포털사이트를 소개합니다.</p>
            </header>
            <section>
              <h2 className="tit_4">조직소개</h2>
              <article>
                <h3 className="tit_5">조직</h3>
                <p className="msg_1">
                  오픈커뮤니티의 초기 정착을 위해 표준프레임워크 개발 참여자와 국내 주요 오픈커뮤니티의 운영자·전문가를 리딩 그룹(PMC, 커미터)으로 구성<br />
                  오픈커뮤니티의 지속적인 확대·발전을 위해 프로젝트 활동에 적극적으로 참여하는 커뮤니티 회원이 리딩그룹의 역할을 획득할 수 있도록 투명하고 공정한 의사결정 체계를 수립
                </p>
              </article>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}

export default EgovAboutOrganization;