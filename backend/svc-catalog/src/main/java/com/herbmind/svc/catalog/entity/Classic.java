package com.herbmind.svc.catalog.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/** classic —— 经典著作（一部语料可含多部经典）。 */
@TableName("classic")
public class Classic {

    @TableId
    private String id;
    private String bookId;
    private String name;
    private String abbr;
    private String dynasty;
    private String pathText;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getBookId() { return bookId; }
    public void setBookId(String bookId) { this.bookId = bookId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getAbbr() { return abbr; }
    public void setAbbr(String abbr) { this.abbr = abbr; }

    public String getDynasty() { return dynasty; }
    public void setDynasty(String dynasty) { this.dynasty = dynasty; }

    public String getPathText() { return pathText; }
    public void setPathText(String pathText) { this.pathText = pathText; }
}
