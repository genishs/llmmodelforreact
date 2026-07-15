import React from 'react';
import { SERVER_URL } from '@/config';

interface Props {
  boardFiles: Array<{ atchFileId: string; fileSn: number }>;
}

const EgovImageGallery: React.FC<Props> = ({ boardFiles }) => {
  const filesTag = boardFiles.map((item, idx) =>
    (
      <React.Fragment key={idx}>
        <img
          src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}&fileSn=${item.fileSn}`}
          alt=""
        />
        <br />
      </React.Fragment>
    )
  );

  // eslint-disable-next-line no-console
  console.log('filesTag : ', filesTag);

  return <div className="board_attach_img">{filesTag}</div>;
};

export default EgovImageGallery;