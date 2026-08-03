import React from "react";
import { SERVER\_URL } from "@/config";

interface EgovImageGalleryProps {
  boardFiles?: any[];
}

function EgovImageGallery({ boardFiles }: EgovImageGalleryProps) {
  let filesTag = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach(function (item, index) {
      filesTag.push(
        \<React.Fragment key={index}\>\<img src={\`\${SERVER\_URL}/image?atchFileId=\${item.atchFileId}&amp; fileSn=\${item.filesn}\`} alt="" /\><br /></React.Fragment\>;
      );
    });
  }
  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return \<div className="board\_attach\_img">{filesTag}</div\>;
}

export default EgovImageGallery;