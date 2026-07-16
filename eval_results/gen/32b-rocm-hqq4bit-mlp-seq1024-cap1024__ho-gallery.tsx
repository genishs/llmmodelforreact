import React from 'react';
import { SERVER_URL } from '@/config';

interface BoardFile {
  atchFileId: string;
  fileSn: number | string;
}

interface Props {
  boardFiles?: BoardFile[];
}

const EgovImageGallery: React.FC<Props> = ({ boardFiles }) => {
  const filesTag: JSX.Element[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        <React.Fragment key={index}>
          <img
            src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}&fileSn=${item.fileSn}`}
            alt=""
          />
          <br />
        </React.Fragment>,
      );
    });
  }

  console.log('filesTag : ', filesTag);
  console.groupEnd('EgovAttachFile');

  return <div className="board_attach_img">{filesTag}</div>;
};

export default EgovImageGallery;