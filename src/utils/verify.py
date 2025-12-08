from DrissionPage import ChromiumPage
import base64
import time
import ddddocr

# 缺口识别函数
def read_img():
    with open("bg.jpg", 'rb') as f:
        bg_bytes = f.read()
    with open("full.jpg", 'rb') as f:
        full_bytes = f.read()
 
    slide = ddddocr.DdddOcr(det=False, ocr=False)
    res = slide.slide_comparison(bg_bytes, full_bytes)
    return res.get("target")[0]

def move_to_and_click_verification():
    # Create a ChromiumPage object
    page = ChromiumPage()
    
    try:
        while True:
            # Navigate to the captcha page
            page.get('https://xueqiu.com/service/captcha')
        
            # Wait for the page to load
            time.sleep(3)

            # 点击验证按钮
            page.ele('xpath://div[@class="geetest_btn"]/div[@class="geetest_radar_btn"]').click()
            time.sleep(2)


            # 获取背景图和滑块图
            bg_src = page.run_js(
                "return document.getElementsByClassName('geetest_canvas_bg geetest_absolute')[0].toDataURL('image/png')")
            full_src = page.run_js(
                "return document.getElementsByClassName('geetest_canvas_fullbg geetest_fade geetest_absolute')[0].toDataURL('image/png')")
 
            # 处理图片数据并保存
            bg_data = base64.b64decode(bg_src.split(',')[1].encode('utf-8'))
            with open("bg.jpg", 'wb') as f:
                f.write(bg_data)
    
            full_data = base64.b64decode(full_src.split(',')[1].encode('utf-8'))
            with open("full.jpg", 'wb') as f:
                f.write(full_data)
 
            # 计算滑块需要移动的距离
            dis = read_img()
    
            # slide_btn = page.ele('css:div.geetest_slider_button')

            # 模拟人类滑动操作
            slide_btn = page.ele('css:div.geetest_slider_button')
            actions = page.actions
            actions.move_to(slide_btn)
            actions.m_hold(slide_btn)
            time.sleep(0.2)

            actions.move(dis - 10, 0)
            time.sleep(0.2)
            actions.move(10, 0)
            time.sleep(0.2)
            actions.move(-10, 0)
            actions.m_release(slide_btn)

            time.sleep(2)

            if page.ele('@text()=关于雪球'):
                print("Captcha passed successfully!")
                page.quit()
                break
            else:
                print("Captcha failed. Please try again.")
                
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()